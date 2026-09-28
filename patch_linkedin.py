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



def swap(src, old, new, name):
    if new in src:
        return src
    if old not in src:
        raise SystemExit(f"patch failed: {name}: {old[:70]!r}")
    return src.replace(old, new)


ES_LABELS = {
    "easy apply": "solicitud sencilla", "next": "siguiente", "continue to next step": "siguiente paso", "review": "revisar",
    "review your application": "revisar tu solicitud", "submit application": "enviar solicitud", "discard": "descartar",
    "done": "listo", "continue": "continuar", "all filters": "todos los filtros", "show results": "mostrar resultados",
    "most recent": "más recientes", "most relevant": "más relevantes", "any time": "cualquier momento",
    "past month": "último mes", "past week": "última semana", "past 24 hours": "últimas 24 horas",
    "internship": "prácticas", "entry level": "sin experiencia", "associate": "algo de responsabilidad",
    "mid-senior level": "intermedio", "director": "director", "executive": "ejecutivo", "full-time": "jornada completa",
    "part-time": "media jornada", "contract": "contrato", "temporary": "temporal", "volunteer": "voluntario",
    "other": "otro", "on-site": "presencial", "remote": "remoto", "hybrid": "híbrido",
    "under 10 applicants": "menos de 10 solicitudes", "in your network": "en tu red",
    "fair chance employer": "segunda oportunidad", "sign in": "iniciar sesión", "join now": "únete ahora", "cancel": "cancelar",
}
ES_QUESTION_TERMS = [
    ("años", "years"), ("experiencia", "experience"), ("salario", "salary"), ("sueldo", "salary"),
    ("remuneración", "salary"), ("pretensión salarial", "expected salary"), ("teléfono", "phone"), ("móvil", "mobile"),
    ("celular", "mobile"), ("correo electrónico", "email"), ("ciudad", "city"), ("país", "country"),
    ("código postal", "zip code"), ("dirección", "address"), ("provincia", "state"), ("nombre completo", "full name"),
    ("apellido", "last name"), ("nombre", "first name"), ("sitio web", "website"), ("carta de presentación", "cover letter"),
    ("patrocinio", "sponsorship"), ("visado", "visa"), ("autorizado para trabajar", "authorized to work"),
    ("autorización de trabajo", "work authorization"), ("preaviso", "notice period"), ("inglés", "english"),
    ("ciudadanía", "citizenship"), ("discapacidad", "disability"), ("veterano", "veteran"), ("género", "gender"),
    ("etnia", "ethnicity"), ("resumen", "summary"), ("titular", "headline"), ("reubicarse", "relocate"),
    ("trabajo remoto", "remote work"), ("desplazarse", "commute"),
]
i18n = ('ES_LABELS = ' + repr(ES_LABELS) + '\n'
        'def label_variants(text):\n'
        '    low = text.strip().lower()\n'
        '    return [low] + ([ES_LABELS[low]] if low in ES_LABELS else [])\n\n\n'
        'def text_xpath(tag: str, text: str) -> str:\n'
        '    lower = \'translate(normalize-space(.), "ABCDEFGHIJKLMNOPQRSTUVWXYZÁÉÍÓÚÑ", "abcdefghijklmnopqrstuvwxyzáéíóúñ")\'\n'
        '    return f".//{tag}[" + " or ".join(f\'contains({lower}, "{v}")\' for v in label_variants(text)) + "]"\n\n'
        'def _english_text_xpath(')
clickers_path = bot.parent / "modules" / "clickers_and_finders.py"
clickers = clickers_path.read_text(encoding="utf-8")
clickers = swap(clickers, "def text_xpath(", i18n, "clickers text_xpath")
clickers_path.write_text(clickers, encoding="utf-8")

helpers_path = bot.parent / "modules" / "helpers.py"
helpers = helpers_path.read_text(encoding="utf-8")
helpers = swap(helpers, "    import re\n    match = re.search(r'(\\d+)\\s+(second|minute",
               "    import re\n"
               "    es = {'segundo': 'second', 'minuto': 'minute', 'hora': 'hour', 'día': 'day', 'dia': 'day', 'semana': 'week', 'mes': 'month', 'año': 'year'}\n"
               "    es_match = re.search(r'hace\\s+(\\d+)\\s+(segundo|minuto|hora|día|dia|semana|mes|año)', time_string, re.IGNORECASE)\n"
               "    if es_match: time_string = f'{es_match.group(1)} {es[es_match.group(2).lower()]} ago'\n"
               "    match = re.search(r'(\\d+)\\s+(second|minute", "date es")
helpers_path.write_text(helpers, encoding="utf-8")

es_to_en = ('ES_QUESTION_TERMS = ' + repr(ES_QUESTION_TERMS) + '\n'
            'def es_to_en(label):\n'
            '    rest, extra = label, []\n'
            '    for es, en in sorted(ES_QUESTION_TERMS, key=lambda t: -len(t[0])):\n'
            '        if es in rest:\n'
            '            rest, extra = rest.replace(es, " "), extra + [en]\n'
            '    return label + " " + " ".join(extra) if extra else label\n\n\n'
            'def label_has(')
text = swap(text, "def label_has(", es_to_en, "es_to_en")
text = swap(text, "label = label_org.lower()", "label = es_to_en(label_org.lower())", "label normalize")
text = swap(text, 'candidate_phrases = ["Decline", "not wish", "don\'t wish", "Prefer not", "not want"]',
            'candidate_phrases = ["Decline", "not wish", "don\'t wish", "Prefer not", "not want", "Prefiero no", "No deseo", "No quiero"]', "decline es")
text = swap(text, 'candidate_phrases = ["Yes", "Agree", "I do", "I have"]',
            'candidate_phrases = ["Yes", "Agree", "I do", "I have", "Sí", "Si", "Acepto", "De acuerdo"]', "yes es")
text = swap(text, 'candidate_phrases = ["No", "Disagree", "I don\'t", "I do not"]',
            'candidate_phrases = ["No", "Disagree", "I don\'t", "I do not", "No acepto"]', "no es")
text = swap(text, """next_button_xpath = './/button[@aria-label="Continue to next step" or contains(normalize-space(.), "Next")]'""",
            """next_button_xpath = './/button[@aria-label="Continue to next step" or contains(normalize-space(.), "Next") or contains(@aria-label, "siguiente paso") or contains(normalize-space(.), "Siguiente")]'""", "next")
text = swap(text, """review_button_xpath = './/button[@aria-label="Review your application" or normalize-space(.)="Review"]'""",
            """review_button_xpath = './/button[@aria-label="Review your application" or normalize-space(.)="Review" or contains(@aria-label, "Revisar") or normalize-space(.)="Revisar"]'""", "review")
text = swap(text, """submit_button_xpath = './/button[@aria-label="Submit application" or normalize-space(.)="Submit application"]'""",
            """submit_button_xpath = './/button[@aria-label="Submit application" or normalize-space(.)="Submit application" or contains(@aria-label, "Enviar solicitud") or normalize-space(.)="Enviar solicitud"]'""", "submit")
text = swap(text, """contains(normalize-space(.), 'Discard')]\"""", """contains(normalize-space(.), 'Discard') or contains(normalize-space(.), 'Descartar')]\"""", "discard")
text = swap(text, """contains(@aria-label, 'Easy Apply')]\"""", """(contains(@aria-label, 'Easy Apply') or contains(@aria-label, 'Solicitud sencilla'))]\"""", "easy apply aria")
text = swap(text, """[.//span[contains(normalize-space(.), 'Easy Apply')]]\"""", """[.//span[contains(normalize-space(.), 'Easy Apply') or contains(normalize-space(.), 'Solicitud sencilla')]]\"""", "easy apply span")
text = swap(text, """".//input[@aria-label='City, state, or zip code'and not(@disabled)]\"""",
            """".//input[(@aria-label='City, state, or zip code' or contains(@aria-label, 'Ciudad') or contains(@id, 'jobs-search-box-location')) and not(@disabled)]\"""", "location")
text = swap(text, """".//button[@aria-label='Cancel']\"""", """".//button[@aria-label='Cancel' or @aria-label='Cancelar']\"""", "cancel")
text = swap(text, """'//button[normalize-space()="All filters"]'""", """'//button[normalize-space()="All filters" or normalize-space()="Todos los filtros"]'""", "all filters")
text = swap(text, """'.//span[contains(normalize-space(), " ago")]'""", """'.//span[contains(normalize-space(), " ago") or contains(normalize-space(), "hace ")]'""", "ago")
text = swap(text, """f".//button[@aria-label='Page {current_page+1}']\"""", """f".//button[@aria-label='Page {current_page+1}' or @aria-label='Página {current_page+1}']\"""", "page")

bot.write_text(text, encoding="utf-8")
print("linkedin-bot patched")
