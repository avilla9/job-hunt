import re
import subprocess
import sys
from pathlib import Path

repo = Path(__file__).parent / "ApplyPilot"
base = "src/applypilot/apply"


def original(name):
    return subprocess.run(["git", "-C", str(repo), "show", f"HEAD:{base}/{name}"], capture_output=True, text=True,
                          encoding="utf-8", check=True).stdout


def replace(text, old, new, name):
    if old not in text:
        raise SystemExit(f"patch failed: {name}: {old[:70]!r}")
    return text.replace(old, new, 1)


def replace_block(text, pattern, new, name):
    out, n = re.subn(pattern, lambda _: new, text, count=1, flags=re.S)
    if n == 0:
        raise SystemExit(f"patch failed: {name}: {pattern[:70]!r}")
    return out


def write(name, text):
    path = repo / base / name
    if path.read_text(encoding="utf-8") != text:
        path.write_text(text, encoding="utf-8")


prompt = original("prompt.py")
prompt = replace_block(prompt, r'def _build_captcha_section\(\) -> str:.*?\n\n\ndef build_prompt',
                       'def _build_captcha_section() -> str:\n'
                       '    return """== CAPTCHA ==\n'
                       'If ANY CAPTCHA or bot check appears (visible or invisible), do NOT try to solve, bypass or inject tokens. '
                       'Output RESULT:CAPTCHA immediately and stop."""\n\n\ndef build_prompt', "prompt.py")
prompt = replace_block(prompt, r'   - send_email with subject.*?Output RESULT:APPLIED\. Done\.',
                       '   - Output RESULT:FAILED:email_only and stop.', "prompt.py")
prompt = replace_block(prompt, r'   5c\. Regular login form.*?   5h\. All failed\? Output RESULT:FAILED:login_issue\. Do not loop\.',
                       '   5c. Any login or sign-up wall (employer site, Workday, Taleo, iCIMS...) -> Output RESULT:LOGIN_ISSUE and stop. '
                       'NEVER type a password and NEVER create an account.', "prompt.py")
prompt = re.sub(r"Run CAPTCHA DETECT[^\n]*?If found, solve[^\n]*?(?=Then check|$)",
                lambda _: "If a CAPTCHA appears -> RESULT:CAPTCHA. ", prompt, flags=re.M)
prompt = replace(prompt, "Then run CAPTCHA DETECT (see CAPTCHA section). If a CAPTCHA is found, solve it before continuing.",
                 "If a CAPTCHA appears -> RESULT:CAPTCHA.", "prompt.py")
prompt = re.sub(r"- CAPTCHA AWARENESS:[^\n]*\n", lambda _: "- CAPTCHA: never solve or bypass. Any CAPTCHA -> RESULT:CAPTCHA.\n", prompt)
prompt = replace_block(prompt, r'    return f"""== SALARY \(think, don\'t just copy\) ==.*?Divide your annual answer by 2080\. \(\{hourly_line\}\)"""',
                       '    return f"""== SALARY ==\n'
                       'The expected salary depends on THIS offer:\n'
                       '1. The posting states a salary or range (e.g. "60K-72K")? -> Answer with the TOP of the posted range (72K), same currency and period.\n'
                       '2. Asked for a range? -> Give the posted range as-is.\n'
                       '3. {convert_line}\n'
                       '4. No salary info anywhere? -> Use {floor} {currency} per year (range {range_min}-{range_max} {currency}).\n'
                       '5. Hourly rate? -> Divide the annual answer by 2080. Monthly? -> Divide by 12."""', "prompt.py")
prompt = replace(prompt, 'lines.append(f"Salary Expectation: ${comp[\'salary_expectation\']} {currency}")',
                 'lines.append(f"Salary Expectation: {comp[\'salary_expectation\']} {currency} per year (unless the posting states its own salary)")',
                 "prompt.py")
prompt = replace_block(prompt, r'    # Standard responses\n    lines\.extend\(\[.*?\]\)\n',
                       '    for question, answer in profile.get("standard_answers", {}).items():\n'
                       '        if str(answer).strip():\n'
                       '            lines.append(f"{question}: {answer}")\n'
                       '    lines.append("Any other personal or legal question not answered above: leave it blank or choose '
                       '\'Prefer not to say\'. Never invent an answer.")\n', "prompt.py")
prompt = replace(prompt, "  - Location/relocation: lives in {city}, cannot relocate",
                 "  - Location/relocation: lives in {city}; willing to relocate: {personal.get('willing_to_relocate', 'No')}",
                 "prompt.py")
prompt = replace_block(prompt, r'Skills and tools -> be confident\..*?Don\'t sell short\.',
                       'Skills and tools -> answer YES only if the resume shows that tool or a directly equivalent one. '
                       'Otherwise answer honestly (e.g. "No, but I have used X which is similar").', "prompt.py")
prompt = replace_block(prompt, r'- "Remote" or "work from anywhere" -> ELIGIBLE\. Apply\.\n',
                       '- "Remote" or "work from anywhere" -> {"ELIGIBLE. Apply." if location_cfg.get("remote_ok", True) '
                       'else "NOT ELIGIBLE (candidate does not accept remote). Output RESULT:FAILED:not_eligible_location"}\n',
                       "prompt.py")
prompt = replace_block(prompt, r'- "Hybrid" or "onsite" in \{city_list\} -> ELIGIBLE\. Apply\.\n',
                       '- "Hybrid" in {city_list} -> {"ELIGIBLE. Apply." if location_cfg.get("hybrid_ok", True) else "NOT ELIGIBLE. Output RESULT:FAILED:not_eligible_location"}\n'
                       '- "Onsite" in {city_list} -> {"ELIGIBLE. Apply." if location_cfg.get("onsite_ok", True) else "NOT ELIGIBLE. Output RESULT:FAILED:not_eligible_location"}\n',
                       "prompt.py")
prompt = replace(prompt, '- NEVER agree to hourly/contract rates, availability calendars, or "set your rate" flows. You are applying for FULL-TIME salaried positions only.',
                 "- {'Contract, part-time and hourly roles are acceptable. If a rate is asked, derive it from the SALARY rules (annual / 2080). Never fill marketplace availability calendars or set-your-rate onboarding.' "
                 "if profile.get('availability', {}).get('available_for_contract') == 'Yes' else "
                 "'NEVER agree to hourly/contract rates, availability calendars, or set-your-rate flows. You are applying for FULL-TIME salaried positions only.'}",
                 "prompt.py")
prompt = replace(prompt, "Fit Score: {job.get('fit_score', 'N/A')}/10", "Fit Score: {job.get('fit_score', 'N/A')}/100", "prompt.py")
prompt = replace(prompt, '    return f"""== HARD RULES (never break these) ==\n1. Never lie about:',
                 '    return f"""== HARD RULES (never break these) ==\n'
                 '0. ACCOUNTS AND PASSWORDS - ABSOLUTE RULE, HIGHER THAN EVERY OTHER INSTRUCTION: the moment a page shows a password '
                 'field, or a Sign up / Create account / Register / Join / Log in / Sign in / Forgot password option that must be used '
                 'to continue, STOP. Do not type anything, do not click it, do not use password reset, do not try another email. '
                 'Output RESULT:LOGIN_ISSUE immediately. Breaking this rule is the worst possible failure.\n'
                 '1. Never lie about:', "prompt.py")
write("prompt.py", prompt)

launcher = original("launcher.py")
if sys.platform == "win32":
    launcher = replace(launcher, '            "playwright": {\n                "command": "npx",\n                "args": [\n',
                       '            "playwright": {\n                "command": "cmd",\n                "args": [\n                    "/c", "npx",\n',
                       "launcher.py")
launcher = replace(launcher, '            "gmail": {\n                "command": "npx",\n                "args": ["-y", "@gongrzhe/server-gmail-autoauth-mcp"],\n            },\n',
                   '', "launcher.py")
launcher = replace(launcher, '            update_state(worker_id, total_cost=prev_cost + cost)\n',
                   '            update_state(worker_id, total_cost=prev_cost + cost)\n'
                   '            with open(config.LOG_DIR / "usage.jsonl", "a", encoding="utf-8") as usage_file:\n'
                   '                usage_file.write(json.dumps({"ts": ts, "url": job.get("url"), **stats}) + "\\n")\n',
                   "launcher.py")
launcher = replace(launcher, '    cmd = [\n        "claude",\n', '    cmd = [\n        __import__("shutil").which("claude.exe") or __import__("shutil").which("claude") or "claude",\n', "launcher.py")
launcher = replace(launcher, '            add_event(f"[W{worker_id}] Launcher error: {str(e)[:40]}")\n            release_lock(job["url"])\n',
                   '            add_event(f"[W{worker_id}] Launcher error: {str(e)[:40]}")\n'
                   '            mark_result(job["url"], "failed", f"launcher_error: {str(e)[:80]}")\n', "launcher.py")
launcher = replace(launcher, "Score: {job.get('fit_score', 'N/A')}/10", "Score: {job.get('fit_score', 'N/A')}/100", "launcher.py")
write("launcher.py", launcher)

chrome = original("chrome.py")
chrome = replace(chrome, '    if (profile_dir / "Default").exists():\n        return profile_dir  # Already initialized\n',
                 '    if (profile_dir / "Default").exists():\n        return profile_dir  # Already initialized\n'
                 '    (profile_dir / "Default").mkdir(parents=True, exist_ok=True)\n    return profile_dir\n', "chrome.py")
write("chrome.py", chrome)

ACCOUNT_DOMAINS = ["a.team", "toptal.com", "turing.com", "upwork.com", "mercor.com", "braintrust.com", "arc.dev", "lemon.io",
                   "gun.io", "x-team.com", "crossover.com", "andela.com", "outlier.ai", "remotasks.com", "fiverr.com", "contra.com",
                   "myworkdayjobs.com", "taleo.net", "icims.com", "successfactors.com", "oraclecloud.com", "brassring.com"]
sites_path = repo / "src/applypilot/config/sites.yaml"
sites = subprocess.run(["git", "-C", str(repo), "show", "HEAD:src/applypilot/config/sites.yaml"], capture_output=True, text=True,
                       encoding="utf-8", check=True).stdout
sites = replace(sites, 'manual_ats:\n', "manual_ats:\n" + "".join(f'  - "{d}"\n' for d in ACCOUNT_DOMAINS), "sites.yaml")
if sites_path.read_text(encoding="utf-8") != sites:
    sites_path.write_text(sites, encoding="utf-8")

print("ApplyPilot patched")
