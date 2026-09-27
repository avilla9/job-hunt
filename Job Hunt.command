#!/bin/bash
cd "$(dirname "$(readlink "$0" || echo "$0")")" 2>/dev/null || cd "$(dirname "$0")"
URL="http://127.0.0.1:8765"
if curl -s -o /dev/null "$URL"; then
  open "$URL"
  exit 0
fi
echo "Job Hunt está funcionando. No cierres esta ventana."
python3 ui/server.py
