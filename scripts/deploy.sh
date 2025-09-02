#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
cd "$DIR"
echo "[deploy] pulling…"
git fetch origin
git switch main
git reset --hard origin/main
echo "[deploy] restarting web ui…"
sudo systemctl restart gemma-web
sleep 1
sudo systemctl --no-pager --full status gemma-web | sed -n '1,20p'
echo "[deploy] health:"
curl -sS "${WEB_UI_HEALTH:-http://127.0.0.1:5002/health}" || true
echo
