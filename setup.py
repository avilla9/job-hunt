import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import platform_ops as po  # noqa: E402


def step(msg):
    print(f"\n==> {msg}", flush=True)


def run(cmd, cwd=ROOT, **kw):
    print("   $", " ".join(map(str, cmd)), flush=True)
    subprocess.run(cmd, cwd=cwd, check=True, **kw)


def require(tool, hint):
    if not shutil.which(tool):
        sys.exit(f"\nFalta {tool}. {hint}\nInstálalo y vuelve a ejecutar el instalador.")


def sync_vendor():
    lock = json.loads((ROOT / "vendor.lock").read_text(encoding="utf-8"))
    for name, spec in lock.items():
        target = ROOT / name
        if not (target / ".git").exists():
            step(f"Descargando {name}")
            run(["git", "clone", "--filter=blob:none", spec["repo"], str(target)])
        current = subprocess.run(["git", "-C", str(target), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        if current != spec["commit"]:
            step(f"Fijando {name} en la versión probada")
            run(["git", "-C", str(target), "checkout", "--", "."])
            run(["git", "-C", str(target), "fetch", "--quiet", "origin", spec["commit"]])
            run(["git", "-C", str(target), "checkout", "--quiet", spec["commit"]])


def venv(path, packages=(), requirements=None, editable=None):
    if not Path(po.venv_python(path)).exists():
        run([sys.executable, "-m", "venv", str(ROOT / path)])
    pip = [po.venv_python(path), "-m", "pip", "install", "--quiet", "--disable-pip-version-check"]
    if editable:
        run(pip + ["-e", str(ROOT / editable)])
    if requirements:
        run(pip + ["-r", str(ROOT / requirements)])
    if packages:
        run(pip + list(packages))


def shortcut():
    if po.WINDOWS:
        desktop = subprocess.run(["powershell", "-NoProfile", "-Command", "[Environment]::GetFolderPath('Desktop')"],
                                 capture_output=True, text=True).stdout.strip()
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{desktop}\\Job Hunt.lnk');"
                        f"$s.TargetPath='{ROOT / 'Job Hunt.bat'}';$s.WorkingDirectory='{ROOT}';$s.WindowStyle=7;$s.Save()"], check=False)
        return f"{desktop}\\Job Hunt.lnk"
    if po.MAC:
        link = Path.home() / "Desktop" / "Job Hunt.command"
        link.unlink(missing_ok=True)
        link.symlink_to(ROOT / "Job Hunt.command")
        return str(link)
    apps = Path.home() / ".local" / "share" / "applications"
    apps.mkdir(parents=True, exist_ok=True)
    entry = apps / "job-hunt.desktop"
    entry.write_text(f"[Desktop Entry]\nType=Application\nName=Job Hunt\nExec=\"{ROOT / 'job-hunt.sh'}\"\nTerminal=false\n", encoding="utf-8")
    entry.chmod(0o755)
    return str(entry)


def main():
    update = "--update" in sys.argv
    if sys.version_info < (3, 11):
        sys.exit("Se necesita Python 3.11 o superior.")
    require("git", "Descárgalo en https://git-scm.com")
    require("node", "Descarga Node.js LTS en https://nodejs.org")
    sync_vendor()
    step("Preparando el motor de envío (ApplyPilot)")
    venv(".venv-ap", ["python-jobspy", "--no-deps"], editable="ApplyPilot")
    venv(".venv-ap", ["pydantic", "tls-client", "requests", "markdownify", "regex", "pypdf"])
    step("Preparando el bot de LinkedIn")
    venv("linkedin-bot/.venv", requirements="linkedin-bot/requirements.txt")
    step("Preparando el buscador (career-ops)")
    npm = shutil.which("npm") or "npm"
    run([npm, "install", "--no-fund", "--no-audit", "--loglevel=error"], cwd=ROOT / "career-ops")
    run([shutil.which("npx") or "npx", "playwright", "install", "chromium"], cwd=ROOT / "career-ops")
    step("Aplicando salvaguardas")
    for patch in ("patch_careerops.py", "patch_applypilot.py", "patch_linkedin.py"):
        run([sys.executable, str(ROOT / patch)])
    (ROOT / "applypilot-data").mkdir(exist_ok=True)
    (ROOT / "logs").mkdir(exist_ok=True)
    if not update and "--no-shortcut" not in sys.argv:
        step("Creando acceso directo")
        print("   ", shortcut())
    if not shutil.which("claude"):
        print("\nNota: no se encontró Claude Code. Puedes usar Gemini (gratis) o instalar Claude Code desde https://claude.com/claude-code")
    print("\nListo." + ("" if update else " Abre «Job Hunt» desde el escritorio (o el lanzador de esta carpeta)."))


if __name__ == "__main__":
    main()
