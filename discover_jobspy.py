import hashlib
import math
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import store  # noqa: E402
from filters import rejection  # noqa: E402

CO = ROOT / "career-ops"
CACHE = CO / "data" / "jd-cache"
PIPELINE = CO / "data" / "pipeline.md"
MAX_ROLES = int(os.environ.get("JOBSPY_MAX_ROLES", "5"))
MAX_LOCATIONS = int(os.environ.get("JOBSPY_MAX_LOCATIONS", "3"))
PER_SEARCH = 25


def cache_path(url):
    return CACHE / f"{hashlib.sha1(url.encode()).hexdigest()}.txt"


def clean(value):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    return str(value).replace("|", "/").replace("\n", " ").strip()


def indeed_country(name):
    from jobspy.model import Country
    try:
        return Country.from_string(name.lower())
    except ValueError:
        return None


def searches(s):
    remote_only = s["modality"] == ["remote"]
    places = [p for p in s["locations"] if p.strip()][:MAX_LOCATIONS] or [s["country"]]
    for role in s["roles"][:MAX_ROLES]:
        for place in places:
            yield role, place, remote_only


def scrape(role, place, remote_only, s):
    from jobspy import scrape_jobs
    country = indeed_country(s["country"]) if s["country"] else None
    sites = ["linkedin", "google"] + (["indeed"] if country else []) + (["glassdoor"] if country and len(country.value) > 2 else [])
    hours = int(s["max_age_days"]) * 24
    frames = []
    for site in sites:
        kwargs = dict(site_name=[site], search_term=role, location=place, results_wanted=PER_SEARCH,
                      description_format="markdown", verbose=0)
        if site == "google":
            kwargs["google_search_term"] = f"{role} {'remote ' if remote_only else ''}jobs {place} since last month"
        if site == "linkedin":
            kwargs.update(linkedin_fetch_description=True, hours_old=hours, is_remote=remote_only)
        if site in ("indeed", "glassdoor"):
            kwargs["country_indeed"] = s["country"].lower()
            kwargs.update({"is_remote": True} if remote_only else {"hours_old": hours, "distance": int(s["distance_km"] * 0.62)})
        try:
            frames.append(scrape_jobs(**kwargs))
        except Exception as e:
            print(f"  {site} '{role}' @ {place}: {type(e).__name__}: {str(e)[:120]}", flush=True)
    return frames


def insert_pending(text, lines):
    marker = "\n## Processed"
    if marker in text:
        head, tail = text.split(marker, 1)
        return head.rstrip() + "\n" + "\n".join(lines) + "\n" + marker + tail
    if "## Pending" not in text:
        text = text.rstrip() + "\n\n## Pending\n"
    return text.rstrip() + "\n" + "\n".join(lines) + "\n"


def posted_date(value):
    if isinstance(value, datetime):
        return value.date()
    return value if isinstance(value, date) else None


def main():
    db = store.connect()
    s = store.get_settings(db)
    db.close()
    if not s["roles"]:
        print("Sin roles configurados: nada que buscar")
        return
    CACHE.mkdir(parents=True, exist_ok=True)
    if not PIPELINE.exists():
        PIPELINE.write_text("# Pipeline\n\n## Pending\n", encoding="utf-8")
    known = set(PIPELINE.read_text(encoding="utf-8").split())
    batch = CO / "batch" / "batch-input.tsv"
    if batch.exists():
        known |= set(batch.read_text(encoding="utf-8").split())
    cutoff = date.today() - timedelta(days=int(s["max_age_days"]))
    total, skipped = 0, 0
    for role, place, remote_only in searches(s):
        added = []
        for frame in scrape(role, place, remote_only, s):
            for job in frame.to_dict("records"):
                url = clean(job.get("job_url_direct")) or clean(job.get("job_url"))
                title, company, description = clean(job.get("title")), clean(job.get("company")), str(job.get("description") or "")
                if description == "nan":
                    description = ""
                if not url.startswith("http") or url in known:
                    continue
                posted = posted_date(job.get("date_posted"))
                not_remote = str(job.get("is_remote")) == "False"
                if (posted and posted < cutoff) or (remote_only and not_remote) or rejection(title, s) or len(description) < 200:
                    skipped += 1
                    continue
                location = clean(job.get("location")) or place
                cache_path(url).write_text(f"# {title}\nCompany: {company}\nLocation: {location}\nSource: {clean(job.get('site'))}\n\n"
                                           f"{description}", encoding="utf-8")
                added.append(f"- [ ] {url} | {company} | {title} | {location}")
                known.add(url)
        if added:
            PIPELINE.write_text(insert_pending(PIPELINE.read_text(encoding="utf-8"), added), encoding="utf-8")
        total += len(added)
        print(f"  {role} @ {place}: +{len(added)}", flush=True)
    print(f"JobSpy: {total} ofertas nuevas, {skipped} descartadas por filtros")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
