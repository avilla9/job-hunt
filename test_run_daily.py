import shutil
import sqlite3
import tempfile
from pathlib import Path

import run_daily as rd
import store

tmp = Path(tempfile.mkdtemp())
(tmp / "reports").mkdir()
(tmp / "output").mkdir()
(tmp / "output" / "cv-a.pdf").write_bytes(b"%PDF")
(tmp / "reports" / "001-a.md").write_text(
    "# Evaluation: Acme — Senior Full-Stack Engineer\n\n**Score:** 4.3/5\n**Legitimacy:** High Confidence\n"
    "**URL:** https://job-boards.greenhouse.io/acme/jobs/1\n**PDF:** output/cv-a.pdf\n\n"
    "## Machine Summary\n```yaml\nadvertised_comp: \"$60K-$72K USD\"\n```\n", encoding="utf-8")
(tmp / "reports" / "002-b.md").write_text(
    "# Evaluation: Beta — Backend Engineer\n\n**Score:** 3.8/5\n**Legitimacy:** High Confidence\n"
    "**URL:** https://jobs.ashbyhq.com/beta/2\n**PDF:** not generated\nadvertised_comp: null\n", encoding="utf-8")
(tmp / "reports" / "003-c.md").write_text(
    "# Evaluation: Gamma — Java Dev\n\n**Score:** 2.1/5\n**URL:** https://x/3\n**PDF:** not generated\n", encoding="utf-8")
rd.CO = tmp
rd.LI = tmp / "no-linkedin"

reports = {r["company"]: r for r in rd.parse_reports()}
assert set(reports) == {"Acme", "Beta", "Gamma"}
assert reports["Acme"]["score"] == 4.3 and reports["Acme"]["pdf"].endswith("cv-a.pdf")
assert reports["Acme"]["salary"] == "$60K-$72K USD" and reports["Beta"]["salary"] == ""
assert reports["Beta"]["pdf"].endswith("cv.pdf")

ap = sqlite3.connect(":memory:")
ap.execute("CREATE TABLE jobs(url TEXT PRIMARY KEY,title,site,application_url,tailored_resume_path,fit_score,discovered_at,"
           "apply_status,apply_error,applied_at,salary)")
rd.enqueue(ap, reports.values(), 3.5, 30)
rd.enqueue(ap, reports.values(), 3.5, 30)
assert [r[0] for r in ap.execute("SELECT site FROM jobs ORDER BY fit_score DESC")] == ["Acme", "Beta"]

ap.execute("UPDATE jobs SET apply_status='applied' WHERE site='Acme'")
ap.execute("UPDATE jobs SET apply_status='failed', apply_error='captcha' WHERE site='Beta'")
rows = {r["company"]: r for r in rd.source_rows(ap)}
assert rows["Acme"]["status"] == "Enviada" and rows["Acme"]["score"] == 4.3 and rows["Acme"]["salary"] == "$60K-$72K USD"
assert rows["Beta"]["status"] == "Acción requerida" and "CAPTCHA" in rows["Beta"]["action"]

store.DB_PATH = tmp / "jobhunt.db"
db = store.connect()
assert sum(store.upsert_application(db, r, "run1") for r in rows.values()) == 2
assert sum(store.upsert_application(db, r, "run2") for r in rows.values()) == 0
rows["Beta"]["status"] = "Enviada"
assert store.upsert_application(db, rows["Beta"], "run3")
assert db.execute("SELECT COUNT(*) FROM events WHERE url LIKE '%ashby%'").fetchone()[0] == 2
assert store.get_settings(db)["min_score"] == 3.5
store.save_settings(db, {"min_score": 4.0, "not_a_setting": 1})
assert store.get_settings(db)["min_score"] == 4.0 and "not_a_setting" not in store.get_settings(db)
db.close()

shutil.rmtree(tmp, ignore_errors=True)
print("ok")

T = ["Java", ".NET", "C#", "C++", "C", "Assembly", "COBOL"]
for title, want in {"Senior Java Engineer": "Java", "Senior JavaScript Engineer": None, "ASP.NET Developer": ".NET",
                    "Backend Developer (.NET Core)": ".NET", "C# Developer": "C#", "C++ Engineer": "C++",
                    "Embedded C Developer": "C", "Full-Stack Engineer (React/Node)": None, "Tech Lead - Node.js": None,
                    "COBOL Programmer": "COBOL"}.items():
    assert rd.excluded(title, T) == want, (title, rd.excluded(title, T))
print("exclusions ok")

S = {"excluded_tech": T, "languages": ["es", "en"]}
for title, want in {"Senior Full Stack Developer": None, "Desarrollador Backend Senior": None,
                    "Softwareentwickler Backend (m/w/d)": "language German", "Développeur Full Stack": "language French",
                    "Desenvolvedor Full Stack Pleno": "language Portuguese", "Sviluppatore Web": "language Italian",
                    "Ingeniero de Software Senior": None, "Senior Java Engineer": "excluded tech Java"}.items():
    assert rd.rejection(title, S) == want, (title, rd.rejection(title, S))
assert rd.rejection("Desenvolvedor Full Stack", {"excluded_tech": [], "languages": ["es", "en", "pt"]}) is None
print("languages ok")

import discover_jobspy as dj
import platform_ops as po

text = "# Pipeline\n\n## Pending\n- [ ] https://a | A | X\n\n## Processed\n- [x] done\n"
out = dj.insert_pending(text, ["- [ ] https://b | B | Y"])
assert out.index("https://b") < out.index("## Processed") and out.count("## Processed") == 1
assert dj.insert_pending("# Pipeline\n", ["- [ ] https://c | C | Z"]).endswith("## Pending\n- [ ] https://c | C | Z\n")
assert dj.clean(float("nan")) == "" and dj.clean("Dev | Ops") == "Dev / Ops" and dj.clean(None) == ""
assert po.valid_times(["08:00", "25:00", "8.00", "7:05"]) == ["08:00", "7:05"]

store.DB_PATH = Path(tempfile.mkdtemp()) / "runs.db"
db = store.connect()
db.execute("INSERT INTO runs(id, trigger, started_at, status, pid) VALUES('a','manual','x','running',111)")
db.execute("INSERT INTO runs(id, trigger, started_at, status, pid) VALUES('b','manual','x','running',222)")
db.commit()
assert store.clear_stale_runs(db, lambda pid: pid == 222) == ["a"]
assert [r[0] for r in db.execute("SELECT status FROM runs ORDER BY id")] == ["interrupted", "running"]
db.close()
print("robustness ok")

assert rd.SECURITY_RX.search("The password reset email has been sent")
assert rd.SECURITY_RX.search("Now I'm on the A.Team signup form. I'll fill in Armando's details.")
assert not rd.SECURITY_RX.search("The page requires a login. RESULT:LOGIN_ISSUE")
ap2 = sqlite3.connect(":memory:")
ap2.execute("CREATE TABLE jobs(url TEXT PRIMARY KEY,title,site,application_url,tailored_resume_path,fit_score,discovered_at,"
            "apply_status,apply_error,applied_at,salary)")
rd.enqueue(ap2, [{"company": "A.Team", "role": "Senior Engineer", "url": "https://remotive.com/x", "score": 4.8, "pdf": "cv.pdf",
                  "suspicious": False, "salary": ""}], 3.5, 30)
assert ap2.execute("SELECT apply_status, apply_error FROM jobs").fetchone() == ("manual", "manual ATS: plataforma que exige cuenta")
assert rd.classify("manual", "manual ATS: plataforma que exige cuenta")[0] == "Acción requerida"
print("security ok")
