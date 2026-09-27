import json
import re
import subprocess
from pathlib import Path

from filters import LANGS, title_pattern

ROOT = Path(__file__).resolve().parent
CO = ROOT / "career-ops"
AP_DATA = ROOT / "applypilot-data"
LI = ROOT / "linkedin-bot"
NODE_CWD = ROOT / "career-ops"

REMOTE_TERMS = ["Remote", "Worldwide", "Anywhere", "Global"]
BASE_NEGATIVES = ["word:Intern", "Internship", "Praktikant", "Werkstudent", "Thesis", "Trainee", "Apprentice", "Stagiaire",
                  "Pasante", "Becario", "Student"]
REMOTE_BOARDS = ["himalayas", "remotive", "remoteok", "weworkremotely", "workingnomads", "jobicy", "jobspresso", "nodesk",
                 "remotli", "4dayweek"]
TECH_BOARDS = ["hackernews", "pythonorg", "larajobs", "landingjobs", "agentic-jobs"]
BOARD_EXTRA = {"remotli": {"careers_url": "https://remotli.ch/api/jobs"}, "4dayweek": {"careers_url": "https://4dayweek.io/api/jobs"},
               "pythonorg": {"careers_url": "https://www.python.org/jobs/"}}
US_ONLY = ["must be located in the united states", "us-based candidates only", "must reside in the us",
           "authorized to work in the us", "eu residents only", "must be based in the uk", "must be located in europe"]
MODALITY_LI = {"remote": "Remote", "hybrid": "Hybrid", "onsite": "On-site"}
MODALITY_TEXT = {"remote": "remote", "hybrid": "hybrid", "onsite": "on-site"}


def yaml_load(path, fallback=None):
    source = path if path.exists() else fallback
    if not source or not Path(source).exists():
        return {}
    r = subprocess.run(["node", "-e", "process.stdout.write(JSON.stringify(require('js-yaml').load(require('fs').readFileSync(process.argv[1],'utf8'))||{}))",
                        str(source)], cwd=NODE_CWD, capture_output=True, text=True, encoding="utf-8", check=True)
    return json.loads(r.stdout or "{}")


def yaml_dump(path, data):
    subprocess.run(["node", "-e", "let s='';process.stdin.on('data',d=>s+=d).on('end',()=>require('fs').writeFileSync(process.argv[1],"
                                  "require('js-yaml').dump(JSON.parse(s),{lineWidth:200})))", str(path)],
                   cwd=NODE_CWD, input=json.dumps(data), text=True, encoding="utf-8", check=True)


def write_if_changed(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.read_text(encoding="utf-8") != text:
        path.write_text(text, encoding="utf-8")


def remote_ok(s):
    return "remote" in s["modality"]


def location_terms(s):
    return [x for x in s["locations"] if x.strip()] or ([s["country"]] if s["country"] else [])


def rules_block(s):
    rules = []
    terms = [t for t in s["excluded_tech"] if t.strip()]
    if terms:
        rules.append("## Excluded technologies or keywords (hard rule)\n"
                     f"If the role's title or PRIMARY focus is any of: {', '.join(terms)} -> score it 1.0/5 (FAIL), regardless of other fit. "
                     "A passing mention as nice-to-have does not trigger this rule. JavaScript is NOT Java.")
    langs = [LANGS[c] for c in s["languages"] if c in LANGS]
    if langs:
        rules.append("## Languages (hard rule)\n"
                     f"The candidate works only in: {', '.join(langs)}. If the job description is written in another language, "
                     "or requires working proficiency in another language, score it 1.0/5 (FAIL). "
                     "A language listed only as a plus does not trigger this rule.")
    modes = [MODALITY_TEXT[m] for m in s["modality"] if m in MODALITY_TEXT]
    places = location_terms(s)
    if modes:
        onsite_part = (f" Hybrid or on-site roles are acceptable only within {s['distance_km']} km of: {', '.join(places)}."
                       if places and set(s["modality"]) & {"hybrid", "onsite"} else "")
        remote_part = (f" Remote roles must be open to candidates based in: {', '.join(places) or 'the candidate country'}."
                       if remote_ok(s) else "")
        rules.append("## Work arrangement and location (hard rule)\n"
                     f"Accepted work arrangements: {', '.join(modes)}. Read the arrangement from the job description; "
                     f"if it is not one of these, score it 1.0/5 (FAIL).{onsite_part}{remote_part}")
    if int(s["salary_min_month"] or 0) > 0:
        rules.append("## Minimum compensation (hard rule)\n"
                     f"If the posting states compensation clearly below {s['salary_min_month']} {s['currency']} per month "
                     f"({int(s['salary_min_month']) * 12} per year), score it 1.0/5. If no compensation is stated, do not penalize.")
    return "\n\n".join(rules)


def set_managed_block(path, body):
    start, end = "<!-- job-hunt-rules:start -->", "<!-- job-hunt-rules:end -->"
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    text = re.sub(r"\n*<!-- excluded-tech:start -->.*?<!-- excluded-tech:end -->\n?", "\n", text, flags=re.S)
    block = f"{start}\n{body}\n{end}"
    if start in text:
        text = re.sub(re.escape(start) + r".*?" + re.escape(end), lambda _: block, text, flags=re.S)
    else:
        text = text.rstrip() + "\n\n" + block + "\n"
    write_if_changed(path, text.lstrip())


def generated_profile_md(s):
    rows = "\n".join(f"| **{a.get('name', '')}** | {a.get('fit', 'primary')} | {a.get('proof', '')} |" for a in s["archetypes"])
    return (f"# User Profile Context -- career-ops\n\n## Candidate\n{s['headline'] or s['current_title']}. "
            f"{s['years_experience']} years of experience. Based in {s['city']}, {s['country']}.\n\n"
            f"## Target Roles\n{', '.join(s['roles'])}\n\n"
            f"| Archetype | Fit | What they buy (proof) |\n|---|---|---|\n{rows}\n\n"
            "## Scoring guidance\nScore fit against these archetypes and the CV. Adjacent titles with the same core work count as hits. "
            "Never invent experience the CV does not show.\n")


def generated_brief_md(s):
    arch = "\n".join(f"- {a.get('name', '')} ({a.get('fit', 'primary')}): {a.get('proof', '')}" for a in s["archetypes"])
    return (f"# {s['full_name']} — Triage Brief\n\n## Identity\n{s['headline'] or s['current_title']}, "
            f"{s['years_experience']} years. {s['city']}, {s['country']}. Work authorization: {s['work_authorization'] or 'see profile'}.\n\n"
            f"## Target Archetypes\n{arch}\n\n## Quick Scoring Guide\n| Score | Verdict |\n|---|---|\n| >= 3.5 | PASS |\n"
            "| 3.0 - 3.4 | MARGINAL |\n| < 3.0 | FAIL |\n")


def build_portals(s, t):
    t.setdefault("title_filter", {})
    t["title_filter"]["positive"] = s["title_keywords"] or s["roles"]
    t["title_filter"]["negative"] = list(dict.fromkeys(BASE_NEGATIVES + s["title_excludes"] + [title_pattern(x) for x in s["excluded_tech"]]))
    places = location_terms(s)
    allow = places + (REMOTE_TERMS if remote_ok(s) else [])
    t["location_filter"] = {"always_allow": places, "allow": allow}
    if not remote_ok(s):
        t["location_filter"]["block"] = ["Remote"]
    if remote_ok(s):
        t["country_eligibility_filter"] = {"exclusionary": US_ONLY, "inclusive": [p.lower() for p in places] + ["anywhere", "worldwide"]}
    else:
        t.pop("country_eligibility_filter", None)
    t["salary_filter"] = {"min": int(s["salary_min_month"] or 0) * 12, "max": 0, "currency": s["currency"]}
    t["max_posting_age_days"] = int(s["max_age_days"])
    boards = []
    if remote_ok(s):
        boards += [{"name": p, "provider": p, **BOARD_EXTRA.get(p, {}), "enabled": True} for p in REMOTE_BOARDS]
    if s["is_tech"]:
        boards += [{"name": p, "provider": p, **BOARD_EXTRA.get(p, {}), "enabled": True} for p in TECH_BOARDS]
        boards.append({"name": "Get on Board", "provider": "getonbrd",
                       "categories": ["programming", "machine-learning-ai", "data-science-analytics"], "enabled": True})
    boards += [{"name": f"Torre {r}", "provider": "torre", "search": r, "enabled": True} for r in s["roles"][:4]]
    t["job_boards"] = boards
    if s["target_companies"]:
        t["tracked_companies"] = [{"name": c["name"], "careers_url": c["careers_url"], "enabled": True}
                                  for c in s["target_companies"] if c.get("name") and c.get("careers_url")]
    elif not s["is_tech"]:
        t["tracked_companies"] = []
    t.pop("x_excluded_patterns", None)
    return t


AGENCY_OK = ("### Step 1.5 — Agency postings (user standing preference)\n\n"
             "The user has explicitly stated, as a standing preference recorded in their settings, that postings through agencies, "
             "recruiters or talent platforms ARE acceptable. Do not pause or ask for confirmation. If the JD is agency-mediated, set "
             "`via` to the observed agency (or null if unknown), use `?` as company when the end employer is unknown, and continue "
             "with the full evaluation.\n\n")
AGENCY_NO = ("### Step 1.5 — Agency postings (user standing preference)\n\n"
             "The user has explicitly stated, as a standing preference recorded in their settings, that postings through agencies, "
             "recruiters or talent platforms are NOT acceptable. Do not pause or ask for confirmation. If the JD is clearly "
             "agency-mediated, still write the report and tracker line, but with **Score:** 1.0/5 and the verdict "
             "\"Agency posting — skipped by user preference\"; do not generate a PDF.\n\n")


def rewrite_from_head(relpath, pattern, replacement):
    git = subprocess.run(["git", "-C", str(CO), "show", f"HEAD:{relpath}"], capture_output=True, text=True, encoding="utf-8")
    if git.returncode != 0:
        return
    text, n = re.subn(pattern, lambda _: replacement, git.stdout, count=1, flags=re.S)
    if n:
        write_if_changed(CO / relpath, text)


def build_batch_prompt(s):
    rule = AGENCY_OK if s["accept_agencies"] else AGENCY_NO
    body = rule.split("\n\n", 1)[1]
    rewrite_from_head("batch/batch-prompt.md", r"### Step 1\.5 — .*?(?=### Step 2)", rule)
    rewrite_from_head("modes/_shared.md", r"### Agency confirmation handoff.*?(?=\n### )", "### Agency postings (user standing preference)\n\n" + body)
    rewrite_from_head("modes/oferta.md", r"## Agency confirmation gate.*?(?=\n## )", "## Agency postings (user standing preference)\n\n" + body)


def build_career_ops(s):
    build_batch_prompt(s)
    if s["cv_md"].strip():
        write_if_changed(CO / "cv.md", s["cv_md"].strip() + "\n")
    profile = yaml_load(CO / "config" / "profile.yml", CO / "config" / "profile.example.yml")
    cand = profile.setdefault("candidate", {})
    for key, value in {"full_name": s["full_name"], "email": s["email"], "phone": s["phone"], "title": s["current_title"],
                       "location": ", ".join(x for x in (s["city"], s["country"]) if x), "linkedin": s["linkedin_url"],
                       "github": s["github_url"], "portfolio_url": s["github_url"]}.items():
        if value:
            cand[key] = value
    cand["photo"] = ""
    if s["roles"]:
        profile.setdefault("target_roles", {})["primary"] = s["roles"]
    if s["archetypes"]:
        profile.setdefault("target_roles", {})["archetypes"] = [{"name": a.get("name", ""), "level": a.get("level", ""), "fit": a.get("fit", "primary")}
                                                 for a in s["archetypes"]]
    if s["headline"]:
        profile.setdefault("narrative", {})["headline"] = s["headline"]
    comp = profile.setdefault("compensation", {})
    comp["currency"] = s["currency"]
    comp["minimum"] = f"{s['salary_min_month']} {s['currency']}/month" if int(s["salary_min_month"] or 0) else "not specified"
    loc = profile.setdefault("location", {})
    loc.update({"country": s["country"], "city": s["city"], "visa_status": s["work_authorization"],
                "authorized_in": [s["country"]] if s["country"] else [], "needs_sponsorship": s["requires_sponsorship"] == "Yes"})
    profile.setdefault("language", {})["output"] = "en"
    profile["spend_tier"] = "economy"
    profile.setdefault("cv", {})["output_format"] = "html"
    profile.setdefault("cover_letter", {})["notice_period_days"] = int(s["notice_days"])
    profile["auto_pdf_score_threshold"] = 3
    yaml_dump(CO / "config" / "profile.yml", profile)

    for name, generated in (("_profile.md", generated_profile_md), ("_brief.md", generated_brief_md)):
        path = CO / "modes" / name
        if s["generated_modes"]:
            write_if_changed(path, generated(s))
        set_managed_block(path, rules_block(s))

    portals = yaml_load(CO / "portals.yml", CO / "templates" / "portals.example.yml")
    yaml_dump(CO / "portals.yml", build_portals(s, portals))


def build_linkedin(s):
    path = LI / "user_config.json"
    cfg = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    first, _, last = s["full_name"].partition(" ")
    fallback = int(s["salary_fallback_year"] or 0)
    other = [name for code, name in LANGS.items() if code not in s["languages"]]
    lang_phrases = [fmt.format(name) for name in other
                    for fmt in ("fluent in {}", "fluency in {}", "{}-speaking", "{} speaking", "native {}", "{} required", "{} is required")]
    bio = s["headline"] or s["current_title"]
    cfg.setdefault("personals", {}).update({"first_name": first, "middle_name": "", "last_name": last,
                                            "phone_number": re.sub(r"\D", "", s["phone"])[-10:], "current_city": s["city"],
                                            "country": s["country"], "ethnicity": "Decline", "gender": "Decline",
                                            "disability_status": "Decline", "veteran_status": "Decline"})
    q = cfg.setdefault("questions", {})
    q.update({"default_resume_path": str(ROOT / "profile" / "cv.pdf"), "years_of_experience": str(s["years_experience"] or "0"),
              "require_visa": s["requires_sponsorship"], "website": s["github_url"] or s["linkedin_url"],
              "desired_salary": fallback, "current_ctc": fallback, "notice_period": int(s["notice_days"]),
              "recent_employer": s["current_company"], "pause_before_submit": False, "pause_at_failed_question": False})
    q.setdefault("linkedin_headline", bio)
    q.setdefault("user_information_all", f"{bio}\nLocation: {s['city']}, {s['country']}.\nEmail: {s['email']}. Phone: {s['phone']}.")
    sr = cfg.setdefault("search", {})
    sr.update({"search_terms": s["roles"] or sr.get("search_terms", []),
               "search_location": (location_terms(s) or [""])[0], "on_site": [MODALITY_LI[m] for m in s["modality"] if m in MODALITY_LI],
               "date_posted": "Past month" if int(s["max_age_days"]) > 7 else "Past week", "sort_by": "Most relevant",
               "easy_apply_only": True, "pause_after_filters": False, "about_company_bad_words": [],
               "bad_words": ["US Citizen", "USA Citizen", "Security Clearance", "Green Card"]
                            + [x for x in s["excluded_tech"] if len(x) > 1] + lang_phrases})
    cfg.setdefault("settings", {}).update({"run_non_stop": False, "run_in_background": True, "stop_before_submit": False,
                                           "safe_mode": True, "keep_screen_awake": False, "close_tabs": True,
                                           "cycle_date_posted": False, "alternate_sortby": False, "click_gap": 4,
                                           "auto_manage_driver": False})
    cfg.setdefault("secrets", {})["use_AI"] = False
    write_if_changed(path, json.dumps(cfg, indent=2, ensure_ascii=False))


def build_applypilot(s):
    path = AP_DATA / "profile.json"
    ap = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    fallback = str(int(s["salary_fallback_year"] or 0))
    ap.setdefault("personal", {}).update({"full_name": s["full_name"], "preferred_name": s["full_name"].split(" ")[0] if s["full_name"] else "",
                                          "email": s["email"], "password": "", "phone": s["phone"], "city": s["city"],
                                          "country": s["country"], "linkedin_url": s["linkedin_url"], "github_url": s["github_url"],
                                          "willing_to_relocate": s["willing_to_relocate"]})
    ap["work_authorization"] = {"legally_authorized_to_work": s["work_authorization"] or "See profile",
                                "require_sponsorship": s["requires_sponsorship"], "work_permit_type": s["work_authorization"]}
    ap["availability"] = {"earliest_start_date": f"{s['notice_days']} days from offer",
                          "available_for_full_time": "Yes" if "full-time" in s["contract_types"] else "No",
                          "available_for_contract": "Yes" if "contract" in s["contract_types"] else "No"}
    ap["compensation"] = {"salary_expectation": fallback, "salary_currency": s["currency"], "salary_range_min": fallback,
                          "salary_range_max": fallback, "currency_conversion_note": f"Convert the posted figure to {s['currency']}"}
    ap.setdefault("experience", {}).update({"years_of_experience_total": str(s["years_experience"]), "education_level": s["education"],
                                            "current_job_title": s["current_title"], "current_company": s["current_company"],
                                            "target_role": (s["roles"] or [s["current_title"]])[0]})
    ap["standard_answers"] = s["standard_answers"]
    ap.setdefault("eeo_voluntary", {"gender": "Decline to self-identify", "race_ethnicity": "Decline to self-identify",
                                    "veteran_status": "Decline to self-identify", "disability_status": "I do not wish to answer"})
    ap.setdefault("skills_boundary", {})
    ap.setdefault("resume_facts", {})
    write_if_changed(path, json.dumps(ap, indent=2, ensure_ascii=False))
    places = location_terms(s)
    searches = {"queries": [{"query": r, "tier": 1} for r in s["roles"]],
                "location": {"accept_patterns": places + (REMOTE_TERMS if remote_ok(s) else []), "primary": s["city"],
                             "remote_ok": remote_ok(s), "hybrid_ok": "hybrid" in s["modality"], "onsite_ok": "onsite" in s["modality"]},
                "country": s["country"]}
    write_if_changed(AP_DATA / "searches.yaml", json.dumps(searches, indent=2, ensure_ascii=False))


def propagate(s):
    build_career_ops(s)
    build_linkedin(s)
    build_applypilot(s)
