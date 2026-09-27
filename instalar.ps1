$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
Write-Host "Instalando Job Hunt..." -ForegroundColor Cyan

function Refresh-Path {
  $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
}

function Ensure($command, $wingetId, $name) {
  $found = Get-Command $command -ErrorAction SilentlyContinue
  if ($found -and $found.Source -notlike "*WindowsApps*") { return }
  if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    throw "Falta $name y no hay winget. Instala $name manualmente y vuelve a ejecutar Instalar."
  }
  Write-Host "Instalando $name..." -ForegroundColor Yellow
  winget install --id $wingetId -e --silent --accept-source-agreements --accept-package-agreements
  Refresh-Path
}

Ensure "python" "Python.Python.3.12" "Python"
Ensure "node" "OpenJS.NodeJS.LTS" "Node.js"
Ensure "git" "Git.Git" "Git"
$chrome = @("$env:ProgramFiles\Google\Chrome\Application\chrome.exe", "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe", "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe")
if (-not ($chrome | Where-Object { Test-Path $_ })) { Ensure "chrome-missing" "Google.Chrome" "Google Chrome" }

python setup.py
if ($LASTEXITCODE -ne 0) { throw "La instalación no terminó. Revisa el mensaje de arriba." }
Start-Process -FilePath (Join-Path $PSScriptRoot "Job Hunt.bat")
