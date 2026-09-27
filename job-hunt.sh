#!/bin/bash
cd "$(dirname "$0")"
URL="http://127.0.0.1:8765"
if curl -s -o /dev/null "$URL" 2>/dev/null; then
  (xdg-open "$URL" || open "$URL") >/dev/null 2>&1
  exit 0
fi
mkdir -p logs
nohup python3 ui/server.py > logs/ui.log 2>&1 &
