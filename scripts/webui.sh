#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
PORT="${2:-${WEB_UI_PORT:-5002}}"
PID="$DIR/logs/web_ui.${PORT}.pid"
LOG="$DIR/logs/web_ui.${PORT}.log"
DEBUG="${WEB_UI_DEBUG:-0}"

mkdir -p "$DIR/logs"

case "${1:-}" in
  start)
    if [ -f "$PID" ] && kill -0 "$(cat "$PID")" 2>/dev/null; then
      echo "Already running: PID $(cat "$PID") on port $PORT"; exit 0
    fi
    cd "$DIR"
    . venv/bin/activate
    WEB_UI_PORT="$PORT" WEB_UI_DEBUG="$DEBUG" nohup python web_ui.py > "$LOG" 2>&1 &
    echo $! > "$PID"
    echo "Started PID $(cat "$PID") on port $PORT (log: $LOG)"
    ;;
  stop)
    if [ -f "$PID" ]; then
      kill "$(cat "$PID")" 2>/dev/null || true
      rm -f "$PID"
      echo "Stopped port $PORT"
    else
      echo "No pidfile for port $PORT; trying fuser..."
      sudo fuser -k "${PORT}/tcp" || true
    fi
    ;;
  restart)
    "$0" stop "$PORT" || true; sleep 1; "$0" start "$PORT"
    ;;
  status)
    if [ -f "$PID" ] && kill -0 "$(cat "$PID")" 2>/dev/null; then
      echo "Running PID $(cat "$PID") on port $PORT"
    else
      if sudo ss -lptn "sport = :$PORT" | grep -q LISTEN; then
        echo "Listening on $PORT (external process)"; sudo ss -lptn "sport = :$PORT"
      else
        echo "Not running on port $PORT"
      fi
    fi
    ;;
  *)
    echo "Usage: $0 {start|stop|restart|status} [port]"
    exit 1
    ;;
esac
