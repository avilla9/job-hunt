import csv
import json
import os
import re
import shutil
import signal
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

import onboarding
import platform_ops as po
import store
from configgen import propagate
from filters import LANGS, blocked_language, excluded, rejection, title_pattern  # noqa: F401

ROOT = Path(__file__).resolve().parent
CO = ROOT / "career-ops"
AP_DATA = ROOT / "applypilot-data"
AP_DB = AP_DATA / "applypilot.db"
LI = ROOT / "linkedin-bot"
BASH = po.bash_path()
AP_ENV = {"APPLYPILOT_DIR": str(AP_DATA), "PYTHONIOENCODING": "utf-8", "LLM_URL": "none"}
AP_EXE = po.venv_exe(".venv-ap", "applypilot")
BUDGET = {"scan": 3600, "jobspy": 1800, "evaluate": 5 * 3600, "apply": 3 * 3600, "linkedin": 3600}
TOTAL_BUDGET = 10 * 3600

ACTIONS = {
    "captcha": "Aplicar manualmente: el formulario tiene CAPTCHA",
    "login_issue": "Aplicar manualmente: el portal pide cuenta o login",
    "sso_required": "Aplicar manualmente: el portal pide login con Google/Microsoft",
    "email_only": "Enviar CV por email según indica la oferta",
    "manual ATS": "Aplicar manualmente: portal marcado como manual",
}
DISCARDED = ("expired", "not_eligible_location", "not_eligible_work_auth", "older than", "suspicious", "discarded")

RUN_ID = None
DB = None
DEADLINE = None
CHILD = None
STEPS = {}


def log(msg):
    if DB is not None and RUN_ID:
        try:
            DB.execute("INSERT INTO run_logs(run_id, ts, msg) VALUES(?,?,?)", (RUN_ID, store.now(), str(msg)))
            DB.commit()
        except sqlite3.Error:
            pass
    print(msg, flush=True)


def remaining(step):
    left = (DEADLINE - time.time()) if DEADLINE else BUDGET[step]
    return max(60, min(BUDGET[step], left))


def run(cmd, cwd, extra_env=None, timeout=None):
    global CHILD
    log(f"$ {' '.join(map(str, cmd))}")
    group = {"creationflags": po.NO_WINDOW} if po.WINDOWS else {"start_new_session": True}
    p = subprocess.Popen(cmd, cwd=cwd, env={**os.environ, **(extra_env or {})}, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", **group)
    CHILD = p
    timer = threading.Timer(timeout, po.kill_tree, [p.pid]) if timeout else None
    if timer:
        timer.start()
    for line in p.stdout:
        if line.strip():
            log(line.rstrip())
    code = p.wait()
    CHILD = None
    if timer:
        timer.cancel()
    log(f"exit {code}")
    return code


def step(name, code, ok_codes=(0,)):
    STEPS[name] = "OK" if code in ok_codes else f"ERROR (exit {code})"
    return code


def on_terminate(signum, frame):
    if CHILD is not None:
        po.kill_tree(CHILD.pid)
    raise SystemExit(f"detenida por señal {signum}")


def build_batch_input(reject=lambda title: None):
    pipeline = CO / "data" / "pipeline.md"
    lines = pipeline.read_text(encoding="utf-8").splitlines() if pipeline.exists() else []
    pending, dropped = [], 0
    for i, line in enumerate(lines):
        if line.startswith("- [ ] "):
            parts = [p.strip() for p in line[6:].split("|")]
            reason = reject(parts[2] if len(parts) > 2 else "")
            if reason:
                lines[i] = f"- [x] {line[6:]} | skipped: {reason}"
                dropped += 1
            else:
                pending.append(parts)
    if dropped:
        pipeline.write_text("\n".join(lines) + "\n", encoding="utf-8")
    path = CO / "batch" / "batch-input.tsv"
    rows = list(csv.reader(path.open(encoding="utf-8"), delimiter="\t")) if path.exists() else [["id", "url", "source", "notes"]]
    title = lambda r: r[3].split(" | ", 1)[-1] if len(r) > 3 else ""
    before = len(rows)
    rows = [rows[0]] + [r for r in rows[1:] if not reject(title(r))]
    dropped += before - len(rows)
    known = {r[1] for r in rows[1:]}
    next_id = max([int(r[0]) for r in rows[1:]] or [0]) + 1
    added = 0
    for parts in pending:
        if parts[0] not in known:
            rows.append([str(next_id), parts[0], "scan", " | ".join(parts[1:3])])
            known.add(parts[0])
            next_id += 1
            added += 1
    with path.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f, delimiter="\t", lineterminator="\n").writerows(rows)
    log(f"{added} ofertas nuevas para evaluar; {dropped} descartadas por tecnología o idioma")


def parse_reports():
    out = []
    for report in sorted((CO / "reports").glob("*.md")):
        text = report.read_text(encoding="utf-8", errors="replace")
        field = lambda k: (re.search(rf"^\*\*{k}:\*\*\s*(.+)$", text, re.M) or [None, ""])[1].strip()
        head = re.search(r"^# Evaluation:\s*(.+?)\s+[—-]\s+(.+)$", text, re.M)
        score = re.match(r"([\d.]+)(?:\s*/\s*5)?", field("Score"))
        if not (head and score and field("URL")):
            continue
        pdf = field("PDF")
        pdf_path = CO / pdf if pdf.lower().endswith(".pdf") else None
        out.append({"company": head[1], "role": head[2], "url": field("URL"), "score": float(score[1]),
                    "pdf": str(pdf_path) if pdf_path and pdf_path.exists() else str(ROOT / "profile" / "cv.pdf"),
                    "suspicious": field("Legitimacy").lower().startswith("suspicious"),
                    "salary": (re.search(r'^advertised_comp:\s*"?([^"\n]*)"?', text, re.M) or [None, ""])[1].replace("null", "")})
    return out


def ensure_resume_text(pdf, cv_md):
    txt = Path(pdf).with_suffix(".txt")
    if cv_md and not txt.exists():
        txt.write_text(cv_md, encoding="utf-8")


def enqueue(ap, reports, min_score, max_age_days, reject=lambda title: None, cv_md=""):
    added = 0
    for r in reports:
        if r["score"] < min_score:
            continue
        status, error = ("expired", "suspicious") if r["suspicious"] else (None, None)
        reason = reject(r["role"])
        if reason:
            status, error = "expired", f"discarded: {reason}"
        ensure_resume_text(r["pdf"], cv_md)
        cur = ap.execute(
            "INSERT OR IGNORE INTO jobs(url,title,site,application_url,tailored_resume_path,fit_score,discovered_at,apply_status,apply_error,salary)"
            " VALUES(?,?,?,?,?,?,?,?,?,?)",
            (r["url"], r["role"], r["company"], r["url"], r["pdf"], round(r["score"] * 20),
             store.now(), status, error, r.get("salary", "")))
        added += cur.rowcount
    cutoff = (datetime.now() - timedelta(days=max_age_days)).isoformat()
    ap.execute("UPDATE jobs SET apply_status='expired', apply_error='older than max age'"
               " WHERE (apply_status IS NULL OR apply_status='failed') AND applied_at IS NULL AND discovered_at < ?", (cutoff,))
    ap.commit()
    log(f"{added} ofertas nuevas en cola con match >= {min_score}/5")


def classify(status, error):
    error = error or ""
    if status == "applied":
        return "Enviada", ""
    if status is None:
        return "En cola", ""
    if any(k in error for k in DISCARDED):
        return "Descartada", ""
    if status == "manual" or any(k in error for k in ACTIONS):
        return "Acción requerida", next((v for k, v in ACTIONS.items() if k in error), "Revisar y aplicar manualmente")
    return "Fallida", ""


def source_rows(ap, reports=(), min_score=3.5, reject=lambda title: None, manual_apply=False):
    rows = []
    if ap is not None:
        for r in ap.execute("SELECT url,title,site,apply_status,apply_error,fit_score,tailored_resume_path,salary FROM jobs"
                            " WHERE apply_status IS NOT 'in_progress'"):
            state, action = classify(r[3], r[4])
            rows.append({"channel": "ATS/Web", "company": r[2], "role": r[1], "url": r[0], "status": state, "action": action,
                         "detail": r[4] or "", "score": (r[5] or 0) / 20, "resume": r[6] or "", "salary": r[7] or ""})
    queued = {r["url"] for r in rows}
    for r in {r["url"]: r for r in reports}.values():
        if r["url"] in queued:
            continue
        reason, action = reject(r["role"]), ""
        if reason:
            state, detail = "Descartada", reason
        elif r["suspicious"]:
            state, detail = "Descartada", "oferta sospechosa"
        elif r["score"] < min_score:
            state, detail = "Descartada", f"match bajo ({r['score']:.1f}/5)"
        elif manual_apply:
            state, detail, action = "Acción requerida", "lista para aplicar", "Abrir y aplicar con tu CV (envío automático requiere Claude)"
        else:
            state, detail = "En cola", "evaluada, pendiente de envío"
        rows.append({"channel": "ATS/Web", "company": r["company"], "role": r["role"], "url": r["url"], "status": state,
                     "action": action, "detail": detail, "score": r["score"], "resume": r["pdf"], "salary": r.get("salary", "")})
    for name, state in (("all_applied_applications_history.csv", "Enviada"), ("all_failed_applications_history.csv", "Fallida")):
        path = LI / "all excels" / name
        if path.exists():
            for r in csv.DictReader(path.open(encoding="utf-8", errors="replace")):
                if r.get("Job Link"):
                    rows.append({"channel": "LinkedIn Easy Apply", "company": r.get("Company", ""), "role": r.get("Title", ""),
                                 "url": r["Job Link"], "status": state, "action": "",
                                 "detail": r.get("Assumed Reason", "") or "", "score": None, "resume": r.get("Resume", "")})
    return rows


def ap_ready(path=AP_DB):
    if not path.exists():
        return False
    con = sqlite3.connect(path)
    try:
        return bool(con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='jobs'").fetchone())
    finally:
        con.close()


def sync(db, run_id=None):
    s = store.get_settings(db)
    ap = sqlite3.connect(AP_DB) if ap_ready() else None
    try:
        rows = source_rows(ap, parse_reports(), float(s["min_score"]), lambda title: rejection(title, s),
                           manual_apply=s["ai_provider"] != "claude")
        changed = sum(store.upsert_application(db, r, run_id) for r in rows)
    finally:
        if ap is not None:
            ap.close()
    db.commit()
    return changed


def counts(db):
    return {r[0]: r[1] for r in db.execute("SELECT status, COUNT(*) FROM applications GROUP BY status")}


def linkedin_due(s):
    return s["linkedin_last_ok"] != datetime.now().strftime("%Y-%m-%d")


def pending_evaluations():
    r = subprocess.run([BASH, "batch/batch-runner.sh", "--dry-run"], cwd=CO, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", stdin=subprocess.DEVNULL, creationflags=po.NO_WINDOW)
    return "No offers to process" not in r.stdout


def evaluate(s, test=False):
    if s["ai_provider"] == "gemini":
        limit = ["--limit=3"] if test else []
        return step("Evaluación", run(["node", "batch-evaluate-gemini.mjs", f"--concurrency={s['eval_parallel']}", *limit], CO,
                                      {"GEMINI_API_KEY": s["gemini_api_key"]}, timeout=remaining("evaluate")))
    code = 0
    for _ in range(1 if test else 5):
        run(["node", "reserve-report-num.mjs", "--gc"], CO, timeout=120)
        extra = ["--resume-paused"] if (CO / "batch" / "batch-runner.paused").exists() else []
        extra += ["--limit", "3"] if test else []
        code = run([BASH, "batch/batch-runner.sh", "--parallel", str(s["eval_parallel"]), "--min-score", str(s["min_score"]),
                    "--max-retries", "3", *extra], CO, timeout=remaining("evaluate"))
        if test or DEADLINE - time.time() < 900 or not pending_evaluations():
            break
    return step("Evaluación", code, ok_codes=(0, 2))


def test_applypilot_dir():
    target = Path(tempfile.gettempdir()) / "jobhunt-test-applypilot"
    shutil.rmtree(target, ignore_errors=True)
    target.mkdir(parents=True)
    for name in ("profile.json", "searches.yaml", "applypilot.db", "applypilot.db-wal", "applypilot.db-shm", "resume.txt", "resume.pdf"):
        if (AP_DATA / name).exists():
            shutil.copy(AP_DATA / name, target / name)
    return target


def apply(s, test=False):
    run([AP_EXE, "status"], ROOT, AP_ENV, timeout=300)
    if not ap_ready():
        return step("Envío", 1)
    ap = sqlite3.connect(AP_DB)
    ap.execute("UPDATE jobs SET apply_status=NULL WHERE apply_status='in_progress'")
    enqueue(ap, parse_reports(), float(s["min_score"]), int(s["max_age_days"]), lambda title: rejection(title, s), s["cv_md"])
    ap.close()
    sync(DB, RUN_ID)
    env, extra = AP_ENV, ["--limit", "1000"]
    if test:
        env = {**AP_ENV, "APPLYPILOT_DIR": str(test_applypilot_dir())}
        extra = ["--limit", "2", "--dry-run"]
        log("PRUEBA: el envío rellena formularios en una copia de la cola y NO pulsa Enviar")
    return step("Envío", run([AP_EXE, "apply", "--min-score", str(round(float(s["min_score"]) * 20)), "--workers", "1", *extra],
                             ROOT, env, timeout=remaining("apply")))


def linkedin(s, test=False):
    if not po.linkedin_logged_in():
        log("LinkedIn: aún no has iniciado sesión en el perfil del bot (Panel → Iniciar sesión); se omite")
        STEPS["LinkedIn"] = "Omitido: falta iniciar sesión"
        return
    if not test and not linkedin_due(s):
        STEPS["LinkedIn"] = "Ya se ejecutó hoy"
        return
    cfg_path = LI / "user_config.json"
    if test:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        cfg["settings"]["stop_before_submit"] = True
        cfg_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
        log("PRUEBA: LinkedIn rellena Easy Apply y se detiene antes de enviar")
    try:
        code = run([po.venv_python("linkedin-bot/.venv"), "runAiBot.py"], LI,
                   {"LINKEDIN_DAILY_CAP": "2" if test else str(s["linkedin_cap"])}, timeout=remaining("linkedin"))
    finally:
        if test:
            propagate(s)
    step("LinkedIn", code)
    if code == 0 and not test:
        store.save_settings(DB, {"linkedin_last_ok": datetime.now().strftime("%Y-%m-%d")})


def main(trigger="scheduled"):
    global RUN_ID, DB, DEADLINE
    if (ROOT / "STOP").exists():
        print("STOP presente: no se ejecuta")
        return 0
    DB = store.connect()
    store.clear_stale_runs(DB, po.pid_alive)
    if DB.execute("SELECT 1 FROM runs WHERE status='running'").fetchone():
        print("ya hay una ejecución en curso")
        return 0
    if not po.WINDOWS:
        signal.signal(signal.SIGTERM, on_terminate)
    test = trigger == "test"
    s = store.get_settings(DB)
    RUN_ID = datetime.now().strftime("%Y%m%d-%H%M%S")
    DEADLINE = time.time() + TOTAL_BUDGET
    DB.execute("INSERT INTO runs(id, trigger, started_at, status, pid) VALUES(?,?,?,?,?)",
               (RUN_ID, trigger, store.now(), "running", os.getpid()))
    DB.commit()
    before, status = counts(DB), "ok"
    reject = lambda title: rejection(title, s)
    try:
        if not s["onboarded"]:
            raise RuntimeError("Completa el alta (Perfil) antes de ejecutar")
        for patch in ("patch_careerops.py", "patch_applypilot.py", "patch_linkedin.py"):
            subprocess.run([sys.executable, str(ROOT / patch)], cwd=ROOT, check=True, capture_output=True,
                           stdin=subprocess.DEVNULL, creationflags=po.NO_WINDOW)
        onboarding.ensure_cv_pdf(s)
        propagate(s)
        log("salvaguardas y configuración aplicadas a los bots" + (" · MODO PRUEBA (no se envía nada)" if test else ""))
        if s["ats_enabled"] or s["jobspy_enabled"]:
            if s["ats_enabled"]:
                step("Búsqueda en portales", run(["node", "scan.mjs", "--quiet"], CO, timeout=remaining("scan")))
            if s["jobspy_enabled"]:
                env = {"JOBSPY_MAX_ROLES": "1", "JOBSPY_MAX_LOCATIONS": "1"} if test else {}
                step("Búsqueda LinkedIn/Indeed/Google", run([po.venv_python(".venv-ap"), str(ROOT / "discover_jobspy.py")], ROOT, env,
                                                            timeout=remaining("jobspy")))
            build_batch_input(reject)
            evaluate(s, test)
            if s["ai_provider"] == "claude":
                apply(s, test)
        if s["linkedin_enabled"]:
            linkedin(s, test)
        log(f"{sync(DB, RUN_ID)} solicitudes actualizadas")
        if any(v.startswith("ERROR") for v in STEPS.values()):
            status = "partial"
    except BaseException as e:
        status = "stopped" if isinstance(e, SystemExit) else "error"
        STEPS["Error"] = str(e)[:200]
        log(f"ERROR: {e!r}")
    finally:
        after = counts(DB)
        delta = {k: after.get(k, 0) - before.get(k, 0) for k in after if after.get(k, 0) != before.get(k, 0)}
        summary = {**delta, **({"pasos": STEPS} if STEPS else {})}
        DB.execute("UPDATE runs SET finished_at=?, status=?, summary=? WHERE id=?",
                   (store.now(), status, json.dumps(summary, ensure_ascii=False), RUN_ID))
        DB.commit()
        for name, result in STEPS.items():
            log(f"{'✔' if result == 'OK' else '•'} {name}: {result}")
        log("fin")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    if sys.stdout:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "scheduled"))
