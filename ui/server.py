import base64
import json
import os
import secrets
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import onboarding  # noqa: E402
import platform_ops as po  # noqa: E402
import run_daily as rd  # noqa: E402
import store  # noqa: E402
from configgen import propagate  # noqa: E402

PORT = int(os.environ.get("JOBHUNT_PORT", "8765"))
TOKEN = secrets.token_urlsafe(24)


def current_run(db):
    store.clear_stale_runs(db, po.pid_alive)
    run = db.execute("SELECT * FROM runs WHERE status='running' ORDER BY started_at DESC LIMIT 1").fetchone()
    return dict(run) if run else None


_task_cache = {"at": 0, "value": None}


def task_info(fresh=False):
    if fresh or not _task_cache["value"] or time.time() - _task_cache["at"] > 20:
        _task_cache.update(at=time.time(), value=po.schedule_info())
    return _task_cache["value"]


def connections(s):
    prompt = ROOT / "ApplyPilot" / "src" / "applypilot" / "apply" / "prompt.py"
    bot = ROOT / "linkedin-bot" / "runAiBot.py"
    runner = ROOT / "career-ops" / "batch" / "batch-runner.sh"
    read = lambda p: p.read_text(encoding="utf-8") if p.exists() else ""
    ai_ok = bool(shutil.which("claude")) if s["ai_provider"] == "claude" else bool(s["gemini_api_key"])
    items = [
        {"id": "ai", "name": "IA: Claude Code" if s["ai_provider"] == "claude" else "IA: Gemini", "ok": ai_ok,
         "hint": "Evalúa ofertas y rellena formularios" if s["ai_provider"] == "claude"
         else "Evalúa ofertas (el envío automático a portales requiere Claude)", "action": "test-ai"},
        {"id": "node", "name": "Node.js", "ok": bool(shutil.which("node")), "hint": "Necesario para buscar y evaluar"},
        {"id": "bash", "name": "Bash", "ok": Path(po.bash_path()).exists() or bool(shutil.which("bash")), "hint": po.bash_path()},
        {"id": "chrome", "name": "Google Chrome", "ok": bool(po.chrome_path()), "hint": po.chrome_path() or "Instala Google Chrome"},
        {"id": "patches", "name": "Salvaguardas aplicadas", "ok": "do NOT try to solve" in read(prompt)
         and "Self-imposed daily cap" in read(bot) and "JD via ATS public API" in read(runner),
         "hint": "Sin CAPTCHA, cuentas ni contraseñas; tope de LinkedIn; salario por oferta", "action": "patches"},
    ]
    if s["linkedin_enabled"]:
        items.append({"id": "linkedin", "name": "Sesión de LinkedIn (perfil del bot)", "ok": po.linkedin_logged_in(),
                      "hint": "Inicia sesión una vez en la ventana que se abre y ciérrala", "action": "linkedin-login"})
    return items


def eval_progress(min_score):
    batch = ROOT / "career-ops" / "batch"
    state_file, input_file = batch / "batch-state.tsv", batch / "batch-input.tsv"
    rows = [l.split("\t") for l in state_file.read_text(encoding="utf-8", errors="replace").splitlines()[1:] if l.strip()] \
        if state_file.exists() else []
    total = max(len(input_file.read_text(encoding="utf-8").splitlines()) - 1, 0) if input_file.exists() else 0
    score = lambda r: float(r[6]) if len(r) > 6 and r[6].replace(".", "", 1).isdigit() else 0
    return {"total": total, "done": sum(r[2] in ("completed", "skipped", "failed") for r in rows),
            "processing": sum(r[2] == "processing" for r in rows), "failed": sum(r[2] == "failed" for r in rows),
            "passed": sum(score(r) >= float(min_score) for r in rows)}


def usage():
    path = rd.AP_DATA / "logs" / "usage.jsonl"
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()] if path.exists() else []
    tokens = sum(r.get("input_tokens", 0) + r.get("output_tokens", 0) + r.get("cache_read", 0) + r.get("cache_create", 0) for r in rows)
    return {"applies": len(rows), "cost_usd": round(sum(r.get("cost_usd", 0) for r in rows), 2), "tokens": tokens}


_last_sync = {"at": 0}


def auto_sync(db):
    if time.time() - _last_sync["at"] > 10:
        _last_sync["at"] = time.time()
        rd.sync(db)


def public_settings(s):
    return {**s, "gemini_api_key": "••••" if s["gemini_api_key"] else "", "cv_md": s["cv_md"][:200]}


def state():
    db = store.connect()
    try:
        s = store.get_settings(db)
        if s["onboarded"]:
            auto_sync(db)
        return {"running": current_run(db), "paused": (ROOT / "STOP").exists(), "settings": public_settings(s),
                "evaluation": eval_progress(s["min_score"]), "task": task_info(), "counts": rd.counts(db),
                "runs": [dict(r) for r in db.execute("SELECT * FROM runs ORDER BY started_at DESC LIMIT 100")],
                "connections": connections(s), "platform": sys.platform, "usage": usage()}
    finally:
        db.close()


def applications(query):
    db = store.connect()
    if store.get_settings(db)["onboarded"]:
        auto_sync(db)
    sql, args = "SELECT * FROM applications WHERE 1=1", []
    if query.get("status"):
        sql += " AND status = ?"
        args.append(query["status"])
    if query.get("q"):
        sql += " AND (company LIKE ? OR role LIKE ? OR url LIKE ?)"
        args += [f"%{query['q']}%"] * 3
    sql += " ORDER BY CASE status WHEN 'Acción requerida' THEN 0 WHEN 'En cola' THEN 1 ELSE 2 END, score DESC, updated_at DESC LIMIT 2000"
    rows = [dict(r) for r in db.execute(sql, args)]
    db.close()
    return rows


def app_action(url, action):
    mapping = {"applied": ("applied", "manual: aplicada por el usuario", "Enviada"),
               "discard": ("expired", "discarded by user", "Descartada"),
               "retry": (None, None, "En cola")}
    ap_status, ap_error, label = mapping[action]
    if rd.AP_DB.exists():
        ap = sqlite3.connect(rd.AP_DB)
        ap.execute("UPDATE jobs SET apply_status=?, apply_error=?, apply_attempts=0,"
                   " applied_at=CASE WHEN ?='applied' THEN ? ELSE NULL END WHERE url=?",
                   (ap_status, ap_error, ap_status, store.now(), url))
        ap.commit()
        ap.close()
    db = store.connect()
    row = db.execute("SELECT * FROM applications WHERE url=?", (url,)).fetchone()
    if row:
        store.upsert_application(db, {**dict(row), "status": label, "action": "", "detail": ap_error or "reintento manual"},
                                 origin="manual")
        db.commit()
    db.close()


def start_run(trigger="manual"):
    db = store.connect()
    busy, onboarded = current_run(db), store.get_settings(db)["onboarded"]
    db.close()
    if not onboarded:
        return False, "Primero completa tu perfil"
    if busy:
        return False, "Ya hay una ejecución en curso"
    (ROOT / "logs").mkdir(exist_ok=True)
    po.spawn_detached([sys.executable, str(ROOT / "run_daily.py"), trigger], ROOT,
                      ROOT / "logs" / f"task-{datetime.now():%Y%m%d-%H%M%S}.txt")
    return True, "Prueba segura iniciada: no se enviará nada" if trigger == "test" else "Ejecución iniciada"


def stop_run():
    db = store.connect()
    run = current_run(db)
    if run:
        po.kill_tree(run["pid"])
        db.execute("UPDATE runs SET status='stopped', finished_at=? WHERE id=?", (store.now(), run["id"]))
        db.commit()
    db.close()
    return bool(run), "Ejecución detenida" if run else "No había ejecución en curso"


def save_settings(values):
    if values.get("gemini_api_key") == "••••":
        values.pop("gemini_api_key")
    if "cv_md" in values and not (onboarding.PROFILE_DIR / "cv-original.pdf").exists():
        (onboarding.PROFILE_DIR / "cv.pdf").unlink(missing_ok=True)
    db = store.connect()
    store.save_settings(db, values)
    s = store.get_settings(db)
    if not int(s["salary_fallback_year"] or 0) and int(s["salary_min_month"] or 0):
        store.save_settings(db, {"salary_fallback_year": int(s["salary_min_month"]) * 12})
        s = store.get_settings(db)
    db.close()
    if s["onboarded"]:
        onboarding.ensure_cv_pdf(s)
        propagate(s)
        if task_info(fresh=True).get("registered"):
            po.schedule(s["schedule_times"])
            task_info(fresh=True)
    return s


def analyze_cv(body):
    data = base64.b64decode(body["data"])
    if len(data) > 10 * 1024 * 1024:
        raise RuntimeError("El archivo supera 10 MB")
    path = onboarding.save_uploaded_cv(body["filename"], data)
    db = store.connect()
    s = store.get_settings(db)
    db.close()
    profile = onboarding.profile_from_cv(path, s)
    if body.get("apply") and s["onboarded"]:
        save_settings(onboarding.merge_profile(s, profile))
    return profile


def finish_onboarding(values):
    values["onboarded"] = True
    values["generated_modes"] = True
    s = save_settings(values)
    po.schedule(s["schedule_times"])
    task_info(fresh=True)
    start_run()


def update_app():
    out = []
    for cmd in (["git", "pull", "--ff-only"], [sys.executable, str(ROOT / "setup.py"), "--update"]):
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
        out.append((r.stdout + r.stderr).strip()[-400:])
        if r.returncode != 0:
            return False, " | ".join(out)
    return True, "Actualizado. Reinicia la interfaz para cargar la nueva versión."


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", f"{ctype}; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def trusted(self):
        return self.headers.get("Host") in (f"127.0.0.1:{PORT}", f"localhost:{PORT}")

    def do_GET(self):
        try:
            self.handle_get()
        except Exception as e:
            self.send(500, {"error": str(e) or repr(e)})

    def handle_get(self):
        if not self.trusted():
            return self.send(403, {"error": "host"})
        url = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(url.query).items()}
        if url.path == "/":
            html = (Path(__file__).parent / "index.html").read_text(encoding="utf-8").replace("__TOKEN__", TOKEN)
            return self.send(200, html.encode(), "text/html")
        if url.path == "/api/state":
            return self.send(200, state())
        if url.path == "/api/applications":
            return self.send(200, applications(q))
        if url.path == "/api/profile":
            db = store.connect()
            s = store.get_settings(db)
            db.close()
            return self.send(200, {**s, "gemini_api_key": "••••" if s["gemini_api_key"] else ""})
        if url.path == "/api/events":
            db = store.connect()
            rows = [dict(r) for r in db.execute("SELECT * FROM events WHERE url=? ORDER BY id DESC", (q.get("url", ""),))]
            db.close()
            return self.send(200, rows)
        if url.path == "/api/logs":
            db = store.connect()
            rows = [dict(r) for r in db.execute("SELECT * FROM run_logs WHERE run_id=? AND id>? ORDER BY id LIMIT 5000",
                                                (q.get("run", ""), int(q.get("after", 0))))]
            db.close()
            return self.send(200, rows)
        self.send(404, {"error": "not found"})

    def do_POST(self):
        if not self.trusted() or self.headers.get("X-Token") != TOKEN:
            return self.send(403, {"error": "token"})
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        path = urlparse(self.path).path
        payload = {}
        try:
            if path == "/api/run":
                ok, msg = start_run()
            elif path == "/api/test-run":
                ok, msg = start_run("test")
            elif path == "/api/stop":
                ok, msg = stop_run()
            elif path == "/api/pause":
                stop = ROOT / "STOP"
                stop.touch() if body.get("paused") else stop.unlink(missing_ok=True)
                ok, msg = True, "Servicio pausado" if body.get("paused") else "Servicio reanudado"
            elif path == "/api/settings":
                save_settings(body)
                ok, msg = True, "Configuración guardada y aplicada"
            elif path == "/api/onboarding/analyze":
                payload = {"profile": analyze_cv(body)}
                ok, msg = True, "Perfil actualizado desde tu CV y aplicado" if body.get("apply") else "CV analizado"
            elif path == "/api/onboarding/finish":
                finish_onboarding(body)
                ok, msg = True, "Listo: primera búsqueda en marcha y programada cada día"
            elif path == "/api/test-ai":
                db = store.connect()
                s = store.get_settings(db)
                db.close()
                answer = onboarding.ask_ai("Reply with the single word OK.", s, timeout=120).strip()
                ok, msg = "OK" in answer.upper(), f"La IA respondió: {answer[:60]}"
            elif path == "/api/schedule":
                if body.get("enabled"):
                    db = store.connect()
                    times = store.get_settings(db)["schedule_times"]
                    db.close()
                    code, out = po.schedule(times)
                else:
                    code, out = po.unschedule()
                task_info(fresh=True)
                ok, msg = code == 0, out or ("Programación activada" if body.get("enabled") else "Programación desactivada")
            elif path == "/api/linkedin-login":
                chrome = po.chrome_path()
                if not chrome:
                    raise RuntimeError("No se encontró Google Chrome")
                po.linkedin_profile_dir().mkdir(parents=True, exist_ok=True)
                po.open_detached([chrome, f"--user-data-dir={po.linkedin_profile_dir()}", "https://www.linkedin.com/login"])
                ok, msg = True, "Chrome abierto: inicia sesión en LinkedIn y cierra la ventana al terminar"
            elif path == "/api/patches":
                for script in ("patch_careerops.py", "patch_applypilot.py", "patch_linkedin.py"):
                    subprocess.run([sys.executable, str(ROOT / script)], cwd=ROOT, check=True, capture_output=True)
                ok, msg = True, "Salvaguardas aplicadas"
            elif path == "/api/applications/action":
                app_action(body["url"], body["action"])
                ok, msg = True, "Solicitud actualizada"
            elif path == "/api/sync":
                db = store.connect()
                n = rd.sync(db)
                db.close()
                ok, msg = True, f"{n} solicitudes actualizadas"
            elif path == "/api/update":
                ok, msg = update_app()
            else:
                return self.send(404, {"error": "not found"})
        except Exception as e:
            ok, msg = False, str(e) or repr(e)
        self.send(200 if ok else 400, {"ok": ok, "message": msg, **payload})


RESTART = threading.Event()


def watch_code(server):
    files = [*ROOT.glob("*.py"), Path(__file__).resolve()]
    stamp = {f: f.stat().st_mtime for f in files}
    while True:
        time.sleep(3)
        if any(f.exists() and f.stat().st_mtime != m for f, m in stamp.items()):
            RESTART.set()
            server.shutdown()
            return


if __name__ == "__main__":
    if sys.stdout:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Job Hunt en http://127.0.0.1:{PORT}  (no cierres esta ventana)")
    if "--no-browser" not in sys.argv:
        webbrowser.open(f"http://127.0.0.1:{PORT}")
    threading.Thread(target=watch_code, args=(server,), daemon=True).start()
    server.serve_forever()
    server.server_close()
    if RESTART.is_set():
        print("Código actualizado: reiniciando Job Hunt…", flush=True)
        os.execv(sys.executable, [sys.executable, str(Path(__file__).resolve()), "--no-browser"])
