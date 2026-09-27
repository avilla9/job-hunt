import json
import shutil
import tempfile
from pathlib import Path

import configgen as cg
import store

tmp = Path(tempfile.mkdtemp())
co, li, ap = tmp / "career-ops", tmp / "linkedin-bot", tmp / "applypilot-data"
(co / "config").mkdir(parents=True)
(co / "templates").mkdir()
(co / "modes").mkdir()
li.mkdir()
ap.mkdir()
shutil.copy(cg.ROOT / "career-ops" / "config" / "profile.example.yml", co / "config" / "profile.example.yml")
shutil.copy(cg.ROOT / "career-ops" / "templates" / "portals.example.yml", co / "templates" / "portals.example.yml")
cg.CO, cg.LI, cg.AP_DATA = co, li, ap

s = {**store.DEFAULTS, "onboarded": True, "generated_modes": True, "full_name": "Ana Pérez", "email": "ana@example.com",
     "phone": "+57 300 1234567", "city": "Bogotá", "country": "Colombia", "headline": "Marketing Manager B2C",
     "current_title": "Marketing Manager", "years_experience": "7", "roles": ["Marketing Manager", "Brand Manager"],
     "modality": ["hybrid", "onsite"], "locations": ["Bogotá"], "distance_km": 30, "is_tech": False, "currency": "COP",
     "salary_min_month": 8000000, "salary_fallback_year": 120000000, "excluded_tech": ["Ventas en frío"],
     "archetypes": [{"name": "Brand Manager", "fit": "primary", "proof": "Lanzó 3 marcas"}],
     "cv_md": "# Ana Pérez\nMarketing Manager", "standard_answers": {"Are you 18 or older?": "Yes"}}
cg.propagate(s)

portals = cg.yaml_load(co / "portals.yml")
assert portals["title_filter"]["positive"] == ["Marketing Manager", "Brand Manager"]
assert "word:Intern" in portals["title_filter"]["negative"]
assert portals["location_filter"] == {"always_allow": ["Bogotá"], "allow": ["Bogotá"], "block": ["Remote"]}
assert "country_eligibility_filter" not in portals
assert portals["salary_filter"] == {"min": 96000000, "max": 0, "currency": "COP"}
providers = [b["provider"] for b in portals["job_boards"]]
assert "remotive" not in providers and "hackernews" not in providers and providers.count("torre") == 2
assert portals["tracked_companies"] == []

profile = cg.yaml_load(co / "config" / "profile.yml")
assert profile["candidate"]["full_name"] == "Ana Pérez" and profile["location"]["country"] == "Colombia"
assert profile["compensation"]["minimum"] == "8000000 COP/month"

brief = (co / "modes" / "_brief.md").read_text(encoding="utf-8")
assert "Ana Pérez" in brief and "hybrid, on-site" in brief and "30 km of: Bogotá" in brief and "Ventas en frío" in brief
assert (co / "cv.md").read_text(encoding="utf-8").startswith("# Ana Pérez")

linkedin = json.loads((li / "user_config.json").read_text(encoding="utf-8"))
assert linkedin["search"]["on_site"] == ["Hybrid", "On-site"] and linkedin["search"]["search_location"] == "Bogotá"
assert linkedin["personals"]["first_name"] == "Ana" and linkedin["questions"]["desired_salary"] == 120000000

applypilot = json.loads((ap / "profile.json").read_text(encoding="utf-8"))
assert applypilot["personal"]["password"] == "" and applypilot["standard_answers"] == {"Are you 18 or older?": "Yes"}
searches = json.loads((ap / "searches.yaml").read_text(encoding="utf-8"))
assert searches["location"] == {"accept_patterns": ["Bogotá"], "primary": "Bogotá", "remote_ok": False, "hybrid_ok": True, "onsite_ok": True}

cg.propagate(s)
assert cg.yaml_load(co / "portals.yml") == portals

shutil.rmtree(tmp, ignore_errors=True)
print("configgen ok")
