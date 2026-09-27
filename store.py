import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(os.environ.get("JOBHUNT_DB") or Path(__file__).parent / "jobhunt.db")

DEFAULTS = {
    "onboarded": False,
    "ai_provider": "claude",
    "gemini_api_key": "",
    "roles": [],
    "title_keywords": [],
    "seniority": [],
    "modality": ["remote", "hybrid", "onsite"],
    "locations": [],
    "distance_km": 30,
    "is_tech": True,
    "min_score": 3.5,
    "max_age_days": 30,
    "currency": "USD",
    "salary_min_month": 0,
    "salary_fallback_year": 0,
    "contract_types": ["full-time", "contract", "part-time", "freelance"],
    "languages": ["es", "en"],
    "excluded_tech": [],
    "title_excludes": [],
    "target_companies": [],
    "accept_agencies": True,
    "ats_enabled": True,
    "jobspy_enabled": True,
    "linkedin_enabled": False,
    "linkedin_cap": 15,
    "eval_parallel": 3,
    "schedule_times": ["08:00", "20:00"],
    "full_name": "",
    "email": "",
    "phone": "",
    "city": "",
    "country": "",
    "linkedin_url": "",
    "github_url": "",
    "headline": "",
    "current_company": "",
    "current_title": "",
    "years_experience": "",
    "education": "",
    "notice_days": 14,
    "work_authorization": "",
    "requires_sponsorship": "No",
    "willing_to_relocate": "No",
    "archetypes": [],
    "cv_md": "",
    "generated_modes": False,
    "standard_answers": {},
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, trigger TEXT, started_at TEXT, finished_at TEXT,
  status TEXT, pid INTEGER, summary TEXT);
CREATE TABLE IF NOT EXISTS run_logs(id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, ts TEXT, msg TEXT);
CREATE INDEX IF NOT EXISTS run_logs_run ON run_logs(run_id);
CREATE TABLE IF NOT EXISTS applications(url TEXT PRIMARY KEY, channel TEXT, company TEXT, role TEXT, score REAL,
  status TEXT, action TEXT, detail TEXT, resume TEXT, first_seen TEXT, updated_at TEXT, salary TEXT);
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT, ts TEXT, status TEXT,
  detail TEXT, run_id TEXT, origin TEXT);
CREATE INDEX IF NOT EXISTS events_url ON events(url);
"""


def now():
    return datetime.now().isoformat(timespec="seconds")


def connect():
    db = sqlite3.connect(DB_PATH, timeout=30)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    return db


def get_settings(db):
    stored = {r["key"]: json.loads(r["value"]) for r in db.execute("SELECT key, value FROM settings")}
    return {**DEFAULTS, **stored}


def save_settings(db, values):
    for key, value in values.items():
        if key in DEFAULTS:
            db.execute("INSERT OR REPLACE INTO settings(key, value) VALUES(?, ?)", (key, json.dumps(value)))
    db.commit()


def upsert_application(db, row, run_id=None, origin="sync"):
    current = db.execute("SELECT status, detail FROM applications WHERE url = ?", (row["url"],)).fetchone()
    ts = now()
    if current and (current["status"], current["detail"] or "") == (row["status"], row.get("detail") or ""):
        return False
    if current:
        db.execute("UPDATE applications SET channel=?, company=?, role=?, score=?, status=?, action=?, detail=?, resume=?,"
                   " updated_at=?, salary=? WHERE url=?",
                   (row["channel"], row["company"], row["role"], row.get("score"), row["status"], row.get("action", ""),
                    row.get("detail", ""), row.get("resume", ""), ts, row.get("salary", ""), row["url"]))
    else:
        db.execute("INSERT INTO applications VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                   (row["url"], row["channel"], row["company"], row["role"], row.get("score"), row["status"],
                    row.get("action", ""), row.get("detail", ""), row.get("resume", ""), ts, ts, row.get("salary", "")))
    db.execute("INSERT INTO events(url, ts, status, detail, run_id, origin) VALUES(?,?,?,?,?,?)",
               (row["url"], ts, row["status"], row.get("detail", ""), run_id, origin))
    return True
