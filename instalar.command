#!/bin/bash
set -e
cd "$(dirname "$0")"
echo "Instalando Job Hunt..."

python_ok() { command -v python3 >/dev/null && python3 -c 'import sys; sys.exit(sys.version_info < (3, 11))'; }

if ! python_ok || ! command -v node >/dev/null || ! command -v git >/dev/null; then
  if command -v brew >/dev/null; then
    brew install python@3.12 node git
  else
    echo "Faltan Python 3.11+, Node.js o Git."
    echo "Instala Homebrew (https://brew.sh) o descárgalos de python.org, nodejs.org y git-scm.com, y vuelve a abrir este instalador."
    read -r -p "Pulsa Enter para cerrar"
    exit 1
  fi
fi
[ -d "/Applications/Google Chrome.app" ] || { command -v brew >/dev/null && brew install --cask google-chrome || echo "Instala Google Chrome para usar LinkedIn."; }

chmod +x "Job Hunt.command" job-hunt.sh
python3 setup.py
open "Job Hunt.command"
