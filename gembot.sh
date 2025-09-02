#!/usr/bin/env bash
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "This script needs to run with root privileges to access certain directories."
  echo "Attempting to re-run with sudo..."
  exec sudo "$0" "$@"
fi

# --- Paths ---
CODE_DIR="/srv/gemini"                     # Python code + venv + requirements.txt
WORKSPACE_DIR="/srv/gemini_workspace"      # project working directory
ENV_FILE="$CODE_DIR/launcher/config/.env"  # keep env here per your setup
LAUNCHER="$CODE_DIR/launcher/launch_gemini_task.sh"

# --- Sanity checks ---
[[ -x "$LAUNCHER" ]] || { echo "Launcher not found/executable: $LAUNCHER"; exit 1; }
[[ -f "$CODE_DIR/requirements.txt" ]] || { echo "requirements.txt missing in $CODE_DIR"; exit 1; }
[[ -f "$ENV_FILE" ]] || { echo "Env file missing: $ENV_FILE"; exit 1; }

# --- Python env setup (lives in CODE_DIR) ---
echo "Performing one-time setup..."
cd "$CODE_DIR"
if [[ ! -d "venv" ]]; then
  python3 -m venv venv
fi
# shellcheck disable=SC1091
source venv/bin/activate

pip install --upgrade pip >/dev/null 2>&1
pip install -r requirements.txt >/dev/null 2>&1
npm install >/dev/null 2>&1
echo "Setup complete."

# --- Start Web UI if not running ---
WEB_UI_SCRIPT="/srv/gemini/web_ui.py"
PID_FILE="$CODE_DIR/logs/web_ui.pid"

# Check if a process is already running
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null; then
        echo "Web UI is already running (PID: $PID)."
    else
        echo "Found a stale PID file. Removing it."
        rm "$PID_FILE"
    fi
fi

# If the PID file doesn't exist, start the process
if [ ! -f "$PID_FILE" ]; then
  echo "Starting Web UI..."
  nohup "$CODE_DIR/venv/bin/python" "$WEB_UI_SCRIPT" > "$CODE_DIR/logs/web_ui.log" 2>&1 &
  # Store the new PID
  echo $! > "$PID_FILE"
  echo "Web UI started (PID: $(cat "$PID_FILE"))."
fi

# --- Load & export env (so libpq sees PG*/DATABASE_URL) ---
set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a

# Be explicit (belt & suspenders)
export PGHOST="${PGHOST:-localhost}"
export PGPORT="${PGPORT:-5432}"
export PGDATABASE="${PGDATABASE:-gemini_agents}"
export PGUSER="${PGUSER:-gemini_user}"
export PGPASSWORD="${PGPASSWORD:-}"
export DATABASE_URL="${DATABASE_URL:-}"

# --- Switch to workspace as the project folder ---
cd "$WORKSPACE_DIR"

# --- Main Menu Loop ---
while true; do
    echo
    echo "--- Gemini Gembot Menu ---"
    options=(
        "Interactive Mode: Default, for direct interaction."
        "Headless Mode: For single-shot commands."
        "Context-Aware Mode: Interactive session with all files in the current directory as context."
        "Agentic Mode: Autonomous execution of a prompt."
        "Quit"
    )
    select opt in "${options[@]}"; do
        # Regenerate TASK_ID for each new command
        TASK_ID="$(TZ=America/Chicago date +%F-%H%M)"

        case $opt in
            "Interactive Mode: Default, for direct interaction.")
                "$LAUNCHER" "$TASK_ID" "interactive"
                break
                ;;
            "Headless Mode: For single-shot commands.")
                "$LAUNCHER" "$TASK_ID" "headless"
                break
                ;;
            "Context-Aware Mode: Interactive session with all files in the current directory as context.")
                "$LAUNCHER" "$TASK_ID" "context"
                break
                ;;
            "Agentic Mode: Autonomous execution of a prompt.")
                "$LAUNCHER" "$TASK_ID" "agentic"
                break
                ;;
            "Quit")
                echo "Exiting."
                exit 0
                ;;
            *)
                echo "Invalid option $REPLY. Please try again."
                break
                ;;
        esac
    done
done
