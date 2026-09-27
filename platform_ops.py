import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WINDOWS = sys.platform == "win32"
MAC = sys.platform == "darwin"
TASK = "JobHunt-AutoApply"
NO_WINDOW = 0x08000000 if WINDOWS else 0
HOME_DATA = Path.home() / ".job-hunt"


def venv_python(venv):
    return str(ROOT / venv / ("Scripts/python.exe" if WINDOWS else "bin/python"))


def venv_exe(venv, name):
    return str(ROOT / venv / ("Scripts" if WINDOWS else "bin") / (f"{name}.exe" if WINDOWS else name))


def bash_path():
    if WINDOWS:
        for candidate in (r"C:\Program Files\Git\bin\bash.exe", r"C:\Program Files (x86)\Git\bin\bash.exe"):
            if Path(candidate).exists():
                return candidate
        git = shutil.which("git")
        return str(Path(git).parent.parent / "bin" / "bash.exe") if git else "bash"
    return shutil.which("bash") or "/bin/bash"


def chrome_path():
    if WINDOWS:
        for base in (os.environ.get("PROGRAMFILES", r"C:\Program Files"), os.environ.get("PROGRAMFILES(X86)", ""),
                     os.environ.get("LOCALAPPDATA", "")):
            candidate = Path(base) / "Google" / "Chrome" / "Application" / "chrome.exe"
            if base and candidate.exists():
                return str(candidate)
        return None
    if MAC:
        candidate = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
        return str(candidate) if candidate.exists() else None
    return shutil.which("google-chrome") or shutil.which("google-chrome-stable") or shutil.which("chromium")


def linkedin_profile_dir():
    if WINDOWS:
        return Path(r"C:\temp\auto-job-apply-profile")
    if MAC:
        return Path.home() / "Library" / "Application Support" / "Google" / "Chrome" / "auto-job-apply-profile"
    return Path.home() / ".auto-job-apply-profile"


def spawn_detached(cmd, cwd, log_file):
    out = open(log_file, "w", encoding="utf-8")
    if WINDOWS:
        detached = 0x00000008 | 0x00000200 | NO_WINDOW
        try:
            return subprocess.Popen(cmd, cwd=cwd, stdout=out, stderr=subprocess.STDOUT, creationflags=detached | 0x01000000)
        except OSError:
            return subprocess.Popen(cmd, cwd=cwd, stdout=out, stderr=subprocess.STDOUT, creationflags=detached)
    return subprocess.Popen(cmd, cwd=cwd, stdout=out, stderr=subprocess.STDOUT, start_new_session=True)


def open_detached(cmd):
    if WINDOWS:
        return subprocess.Popen(cmd)
    return subprocess.Popen(cmd, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def kill_tree(pid):
    if WINDOWS:
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, creationflags=NO_WINDOW)
        return
    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        pass


def new_process_group():
    return {"creationflags": 0} if WINDOWS else {"start_new_session": True}


def pid_alive(pid):
    if not pid:
        return False
    if WINDOWS:
        r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True, creationflags=NO_WINDOW)
        return str(pid) in r.stdout
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _run_cmd():
    return [sys.executable, str(ROOT / "run_daily.py"), "scheduled"]


def _ps(script):
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", creationflags=NO_WINDOW)
    return r.returncode, (r.stdout + r.stderr).strip()


def _plist_path():
    return Path.home() / "Library" / "LaunchAgents" / "com.jobhunt.autoapply.plist"


CRON_TAG = "# job-hunt-autoapply"


def schedule(times):
    if WINDOWS:
        triggers = ",".join(f"(New-ScheduledTaskTrigger -Daily -At '{t}')" for t in times)
        exe, script = sys.executable, ROOT / "run_daily.py"
        silent = Path(exe).with_name("pythonw.exe")
        exe = str(silent) if silent.exists() else exe
        return _ps(f"$a=New-ScheduledTaskAction -Execute '{exe}' -Argument '\"{script}\" scheduled' -WorkingDirectory '{ROOT}';"
                   "$s=New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 12) -MultipleInstances IgnoreNew;"
                   f"Register-ScheduledTask -TaskName '{TASK}' -Action $a -Trigger @({triggers}) -Settings $s "
                   "-Description 'Job Hunt: busca, puntua y aplica' -Force | Out-Null")
    if MAC:
        intervals = "".join(f"<dict><key>Hour</key><integer>{int(t.split(':')[0])}</integer>"
                            f"<key>Minute</key><integer>{int(t.split(':')[1])}</integer></dict>" for t in times)
        args = "".join(f"<string>{a}</string>" for a in _run_cmd())
        plist = _plist_path()
        plist.parent.mkdir(parents=True, exist_ok=True)
        plist.write_text('<?xml version="1.0" encoding="UTF-8"?>\n<plist version="1.0"><dict>'
                         "<key>Label</key><string>com.jobhunt.autoapply</string>"
                         f"<key>ProgramArguments</key><array>{args}</array>"
                         f"<key>WorkingDirectory</key><string>{ROOT}</string>"
                         f"<key>StartCalendarInterval</key><array>{intervals}</array>"
                         f"<key>StandardOutPath</key><string>{ROOT / 'logs' / 'launchd.log'}</string>"
                         f"<key>StandardErrorPath</key><string>{ROOT / 'logs' / 'launchd.log'}</string>"
                         "</dict></plist>\n", encoding="utf-8")
        subprocess.run(["launchctl", "unload", str(plist)], capture_output=True)
        r = subprocess.run(["launchctl", "load", str(plist)], capture_output=True, text=True)
        return r.returncode, r.stderr.strip()
    current = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
    lines = [l for l in current.splitlines() if CRON_TAG not in l]
    cmd = " ".join(f'"{a}"' for a in _run_cmd())
    lines += [f"{int(t.split(':')[1])} {int(t.split(':')[0])} * * * cd \"{ROOT}\" && {cmd} >> logs/cron.log 2>&1 {CRON_TAG}"
              for t in times]
    r = subprocess.run(["crontab", "-"], input="\n".join(lines) + "\n", capture_output=True, text=True)
    return r.returncode, r.stderr.strip()


def unschedule():
    if WINDOWS:
        return _ps(f"Unregister-ScheduledTask -TaskName '{TASK}' -Confirm:$false")
    if MAC:
        plist = _plist_path()
        subprocess.run(["launchctl", "unload", str(plist)], capture_output=True)
        plist.unlink(missing_ok=True)
        return 0, ""
    current = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
    lines = [l for l in current.splitlines() if CRON_TAG not in l]
    r = subprocess.run(["crontab", "-"], input="\n".join(lines) + "\n", capture_output=True, text=True)
    return r.returncode, r.stderr.strip()


def schedule_info():
    if WINDOWS:
        import json
        code, out = _ps(f"$t=Get-ScheduledTask -TaskName '{TASK}' -ErrorAction SilentlyContinue; if($t){{"
                        "$i=$t|Get-ScheduledTaskInfo; $f={param($d) if($d -and $d.Year -gt 2000){$d.ToString('s')}else{''}};"
                        "@{registered=$true; last=(&$f $i.LastRunTime); next=(&$f $i.NextRunTime)}|ConvertTo-Json -Compress}"
                        "else{'{\"registered\":false}'}")
        try:
            return json.loads(out)
        except ValueError:
            return {"registered": False, "error": out[-300:]}
    if MAC:
        return {"registered": _plist_path().exists()}
    current = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
    return {"registered": CRON_TAG in current}
