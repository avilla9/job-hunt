@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0instalar.ps1"
if errorlevel 1 (
  echo.
  echo La instalacion no termino. Lee el mensaje de arriba.
  pause
)
