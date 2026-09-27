import hashlib
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
MAX_ROLES, MAX_LOCATIONS, PER_SEARCH = 5, 3, 25


def cache_path(url):
    return CACHE / f"{hashlib.sha1(url.encode()).hexdigest()}.txt"


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


def main():
    db = store.connect()
    s = store.get_settings(db)
    if not s["roles"]:
        print("Sin roles configurados: nada que buscar")
        return
    CACHE.mkdir(parents=True, exist_ok=True)
    existing = PIPELINE.read_text(encoding="utf-8") if PIPELINE.exists() else "# Pipeline\n\n## Pending\n"
    known = set(existing.split())
    batch = CO / "batch" / "batch-input.tsv"
    if batch.exists():
        known |= set(batch.read_text(encoding="utf-8").split())
    cutoff = date.today() - timedelta(days=int(s["max_age_days"]))
    added, skipped = [], 0
    for role, place, remote_only in searches(s):
        for frame in scrape(role, place, remote_only, s):
            for job in frame.to_dict("records"):
                url = str(job.get("job_url_direct") or job.get("job_url") or "")
                title, company = str(job.get("title") or ""), str(job.get("company") or "")
                description = str(job.get("description") or "")
                posted = job.get("date_posted")
                if not url.startswith("http") or url in known:
                    continue
                if isinstance(posted, (date, datetime)) and (posted.date() if isinstance(posted, datetime) else posted) < cutoff:
                    skipped += 1
                    continue
                if remote_only and job.get("is_remote") is False or rejection(title, s) or len(description) < 200:
                    skipped += 1
                    continue
                location = str(job.get("location") or place)
                cache_path(url).write_text(f"# {title}\nCompany: {company}\nLocation: {location}\nSource: {job.get('site')}\n\n{description}",
                                           encoding="utf-8")
                added.append(f"- [ ] {url} | {company} | {title} | {location}")
                known.add(url)
        print(f"  {role} @ {place}: {len(added)} nuevas acumuladas", flush=True)
    if added:
        PIPELINE.write_text(existing.rstrip() + "\n" + "\n".join(added) + "\n", encoding="utf-8")
    print(f"JobSpy: {len(added)} ofertas nuevas, {skipped} descartadas por filtros")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
