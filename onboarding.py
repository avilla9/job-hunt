import html
import json
import re
import shutil
import subprocess
import urllib.request
import zipfile
from pathlib import Path

import platform_ops as po

ROOT = Path(__file__).resolve().parent
PROFILE_DIR = ROOT / "profile"

PROMPT = """You are setting up a job-search assistant from a candidate's CV. Read the CV below and answer with ONE JSON object only
(no prose, no code fences) with exactly these keys:
- full_name, email, phone, city, country, linkedin_url, github_url (empty string if absent; github_url may be any portfolio URL)
- headline: one-line professional headline in English
- current_company, current_title, years_experience (number as string), education (highest degree, one line)
- currency: ISO 4217 code of the currency used in the candidate's country (e.g. COP, EUR, MXN; USD if unclear)
- roles: 4 to 10 job titles in English this person should search for, most relevant first
- title_keywords: 15 to 40 short keywords or titles used to match job titles, including English, Spanish and Portuguese variants
- title_excludes: 5 to 15 title words that indicate roles this person clearly does NOT want (e.g. unrelated specialties)
- seniority: list from ["Entry", "Mid", "Senior", "Lead", "Manager", "Director"] that fits
- is_tech: true if the person works in software, data or IT, else false
- archetypes: 3 to 5 objects {"name", "level", "fit" (primary|secondary|adjacent), "proof" (one line of evidence from the CV)}
- cv_md: the full CV rewritten as clean Markdown, faithful to the original. Never invent or embellish anything.

CV:
"""


def pdf_text(path):
    tool = shutil.which("pdftotext") or (r"C:\Program Files\Git\mingw64\bin\pdftotext.exe" if po.WINDOWS else None)
    if tool and Path(tool).exists():
        r = subprocess.run([tool, "-layout", str(path), "-"], capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.stdout.strip():
            return r.stdout
    r = subprocess.run([po.venv_python(".venv-ap"), "-c",
                        "import sys,pypdf;print('\\n'.join(p.extract_text() or '' for p in pypdf.PdfReader(sys.argv[1]).pages))",
                        str(path)], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError("No se pudo leer el PDF (falta pdftotext o pypdf)")
    return r.stdout


def docx_text(path):
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8", errors="replace")
    xml = re.sub(r"</w:p>", "\n", xml)
    xml = re.sub(r"<w:tab/>", "\t", xml)
    return html.unescape(re.sub(r"<[^>]+>", "", xml))


def extract_text(path):
    suffix = Path(path).suffix.lower()
    if suffix == ".pdf":
        return pdf_text(path)
    if suffix == ".docx":
        return docx_text(path)
    if suffix in (".md", ".txt"):
        return Path(path).read_text(encoding="utf-8", errors="replace")
    raise RuntimeError("Formato no soportado: usa PDF, DOCX, MD o TXT")


def gemini_model():
    source = (ROOT / "career-ops" / "gemini-eval.mjs").read_text(encoding="utf-8", errors="replace")
    m = re.search(r"GEMINI_MODEL \|\| '([^']+)'", source)
    return m[1] if m else "gemini-flash-latest"


def ask_ai(prompt, s, timeout=300):
    if s["ai_provider"] == "gemini":
        if not s["gemini_api_key"]:
            raise RuntimeError("Falta la clave de Gemini (Conexiones)")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{gemini_model()}:generateContent"
        body = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode()
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", "x-goog-api-key": s["gemini_api_key"]})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
        return "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"])
    claude = shutil.which("claude")
    if not claude:
        raise RuntimeError("No se encontró Claude Code (claude). Instálalo o elige Gemini en Conexiones")
    r = subprocess.run([claude, "-p", "--model", "haiku"], input=prompt, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"Claude falló: {r.stderr.strip()[-300:]}")
    return r.stdout


def parse_json(text):
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise RuntimeError("La IA no devolvió un perfil válido; inténtalo de nuevo")
    return json.loads(match[0])


def profile_from_cv(path, s):
    text = extract_text(path).strip()
    if len(text) < 200:
        raise RuntimeError("El CV parece vacío o es una imagen escaneada; sube una versión con texto")
    data = parse_json(ask_ai(PROMPT + text[:30000], s))
    keep = ("full_name", "email", "phone", "city", "country", "linkedin_url", "github_url", "headline", "current_company",
            "current_title", "years_experience", "education", "currency", "roles", "title_keywords", "title_excludes", "seniority",
            "is_tech", "archetypes", "cv_md")
    return {k: data[k] for k in keep if k in data}


def md_to_html(md):
    out, in_list = [], False
    for line in md.splitlines():
        text = html.escape(line.strip())
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
        text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
        bullet = re.match(r"^[-*]\s+(.*)", text)
        if bullet and not in_list:
            out.append("<ul>")
            in_list = True
        if not bullet and in_list:
            out.append("</ul>")
            in_list = False
        heading = re.match(r"^(#{1,3})\s+(.*)", text)
        if heading:
            out.append(f"<h{len(heading[1])}>{heading[2]}</h{len(heading[1])}>")
        elif bullet:
            out.append(f"<li>{bullet[1]}</li>")
        elif text:
            out.append(f"<p>{text}</p>")
    if in_list:
        out.append("</ul>")
    style = ("body{font:10.5pt/1.4 Arial,sans-serif;color:#111;margin:0}h1{font-size:18pt;margin:0 0 4px}"
             "h2{font-size:12pt;border-bottom:1px solid #999;margin:14px 0 6px;text-transform:uppercase}"
             "h3{font-size:11pt;margin:10px 0 2px}p{margin:3px 0}ul{margin:3px 0 3px 18px;padding:0}li{margin:1px 0}a{color:#111}")
    return f"<!doctype html><html><head><meta charset='utf-8'><style>{style}</style></head><body>{''.join(out)}</body></html>"


def cv_pdf_from_markdown(md, out_path):
    html_path = Path(out_path).with_suffix(".html")
    html_path.write_text(md_to_html(md), encoding="utf-8")
    script = ("const {chromium}=require('playwright');(async()=>{const b=await chromium.launch();const p=await b.newPage();"
              "await p.goto('file://'+process.argv[1].replace(/\\\\/g,'/'));"
              "await p.pdf({path:process.argv[2],format:'A4',margin:{top:'14mm',bottom:'14mm',left:'14mm',right:'14mm'}});await b.close()})()"
              ".catch(e=>{console.error(e);process.exit(1)})")
    subprocess.run(["node", "-e", script, str(html_path.resolve()), str(Path(out_path).resolve())], cwd=ROOT / "career-ops",
                   check=True, capture_output=True)
    html_path.unlink(missing_ok=True)


def save_uploaded_cv(filename, data):
    PROFILE_DIR.mkdir(exist_ok=True)
    for old in PROFILE_DIR.glob("cv-original.*"):
        old.unlink()
    suffix = Path(filename).suffix.lower()
    target = PROFILE_DIR / f"cv-original{suffix}"
    target.write_bytes(data)
    if suffix == ".pdf":
        shutil.copy(target, PROFILE_DIR / "cv.pdf")
    return target


def ensure_cv_pdf(s):
    pdf = PROFILE_DIR / "cv.pdf"
    if not pdf.exists() and s["cv_md"].strip():
        cv_pdf_from_markdown(s["cv_md"], pdf)
    return pdf
