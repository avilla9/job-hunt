import inspect
from pathlib import Path

import salary

bot = Path(__file__).parent / "linkedin-bot" / "runAiBot.py"
text = bot.read_text(encoding="utf-8")

anchor = ('                    if application_link == "Easy Applied": easy_applied_count += 1\n'
          '                    else:   external_jobs_count += 1\n')
cap = ('                    if easy_applied_count >= int(__import__("os").environ.get("LINKEDIN_DAILY_CAP", "15")):\n'
       '                        globals()["dailyEasyApplyLimitReached"] = True\n'
       '                        print_lg("Self-imposed daily cap reached, stopping.")\n'
       '                        return\n')
if cap not in text:
    if anchor not in text:
        raise SystemExit("patch failed: cap anchor not found in runAiBot.py")
    text = text.replace(anchor, anchor + cap, 1)

helper = inspect.getsource(salary.offer_salary)
fn = "def answer_questions(modal: WebElement, questions_list: set, work_location: str, job_description: str | None = None ) -> set:\n"
per_offer = ('    _offer = offer_salary(job_description)\n'
             '    desired_salary = str(_offer) if _offer else globals()["desired_salary"]\n'
             '    desired_salary_monthly = str(round(_offer / 12)) if _offer else globals()["desired_salary_monthly"]\n'
             '    desired_salary_lakhs = str(round(_offer / 100000, 2)) if _offer else globals()["desired_salary_lakhs"]\n')
if per_offer not in text:
    if fn not in text:
        raise SystemExit("patch failed: answer_questions not found in runAiBot.py")
    text = text.replace(fn, "import re\n" + helper + "\n\n" + fn + per_offer, 1)

bot.write_text(text, encoding="utf-8")
print("linkedin-bot patched")
