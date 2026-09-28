import re
from urllib.parse import urlparse

ACCOUNT_DOMAINS = ["a.team", "toptal.com", "turing.com", "upwork.com", "mercor.com", "braintrust.com", "arc.dev", "lemon.io",
                   "gun.io", "x-team.com", "crossover.com", "andela.com", "outlier.ai", "remotasks.com", "fiverr.com", "contra.com",
                   "myworkdayjobs.com", "taleo.net", "icims.com", "successfactors.com", "oraclecloud.com", "brassring.com",
                   "getonbrd.com", "torre.ai", "weworkremotely.com"]


def needs_account(url):
    host = urlparse(url or "").netloc.lower()
    return any(host == d or host.endswith("." + d) for d in ACCOUNT_DOMAINS)

LANGS = {"es": "Spanish", "en": "English", "pt": "Portuguese", "fr": "French", "de": "German", "it": "Italian",
         "nl": "Dutch", "pl": "Polish"}
TITLE_LANG = {
    "de": r"\([mwdfx]/[mwdfx](/[mwdfx])?\)|entwickler|werkstudent|praktikant|softwareentwicklung|\bingenieur\b",
    "fr": r"d[ée]veloppeu(r|se)|ing[ée]nieur(e)?\s+(logiciel|d[ée]veloppement)|\((h/f|f/h)\)|stagiaire",
    "pt": r"desenvolvedor|engenheir[oa]|\bpleno\b|programador(a)?\s+(pleno|s[êe]nior|j[úu]nior)",
    "it": r"sviluppat(ore|rice)|ingegnere",
    "nl": r"ontwikkelaar",
    "pl": r"programista",
}


def term_regex(term):
    left = r"(?<!\w)" if term[0].isalnum() else ""
    right = r"(?!\w)" if term[-1].isalnum() else r"(?![\w#+])"
    return left + re.escape(term) + right


def excluded(title, terms):
    return next((t for t in terms if t.strip() and re.search(term_regex(t.strip()), title or "", re.I)), None)


def title_pattern(term):
    return f"word:{term}" if term.replace(" ", "").isalnum() else term


def blocked_language(title, allowed):
    return next((code for code, rx in TITLE_LANG.items() if code not in allowed and re.search(rx, title or "", re.I)), None)


def rejection(title, s):
    tech = excluded(title, s["excluded_tech"])
    if tech:
        return f"excluded tech {tech}"
    lang = blocked_language(title, s["languages"])
    return f"language {LANGS[lang]}" if lang else None
