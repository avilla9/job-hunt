@echo off
cd /d "%~dp0"
netstat -ano | findstr "127.0.0.1:8765" | findstr "LISTENING" >nul
if %errorlevel%==0 (
  start "" http://127.0.0.1:8765
  exit /b
)
start "Job Hunt UI (no cerrar)" /min cmd /k python ui\server.py
