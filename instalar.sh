#!/bin/bash
set -e
cd "$(dirname "$0")"
echo "Instalando Job Hunt..."

python_ok() { command -v python3 >/dev/null && python3 -c 'import sys; sys.exit(sys.version_info < (3, 11))'; }
node_ok() { command -v node >/dev/null && [ "$(node -p 'process.versions.node.split(".")[0]')" -ge 18 ]; }

if ! python_ok || ! node_ok || ! command -v git >/dev/null; then
  if command -v apt-get >/dev/null; then
    sudo apt-get update && sudo apt-get install -y python3 python3-venv python3-pip git nodejs npm
  elif command -v dnf >/dev/null; then
    sudo dnf install -y python3 git nodejs npm
  fi
fi
python_ok || { echo "Se necesita Python 3.11 o superior."; exit 1; }
node_ok || { echo "Se necesita Node.js 18 o superior (https://nodejs.org)."; exit 1; }
command -v google-chrome >/dev/null || command -v chromium >/dev/null || echo "Aviso: instala Google Chrome para usar LinkedIn."

chmod +x job-hunt.sh "Job Hunt.command"
python3 setup.py
./job-hunt.sh
