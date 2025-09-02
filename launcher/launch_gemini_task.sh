#!/bin/bash
#
# Gemini CLI Wrapped Launcher
# - Loads env from config/.env
# - Selects API key via select_key.py and shows masked details
# - Ensures @google/gemini-cli is installed and up to date
# - Starts the gemini CLI
#

set -euo pipefail

# --- Helpers ---

mask_key() {
  local k="${1:-}"; local n=${#k}
  if (( n < 8 )); then
    printf '[key too short]'
  else
    printf '%s…%s (len=%d)' "${k:0:4}" "${k: -4}" "$n"
  fi
}

log() { echo "LAUNCHER: $*"; }

# --- Paths ---

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)
PROJECT_ROOT=$(cd -- "$SCRIPT_DIR/.." &>/dev/null && pwd)   # launcher/.. -> project root
GEMINI_CLI="$PROJECT_ROOT/node_modules/.bin/gemini"

have_cmd() { [[ -x "$GEMINI_CLI" ]]; }

installed_gemini_version() {
  if have_cmd; then
    "$GEMINI_CLI" --version 2>/dev/null | head -n1 | sed -E 's/[^0-9]*([0-9]+\.[0-9]+\.[0-9]+).*/\1/' || true
  fi
}

latest_gemini_version() {
  npm view @google/gemini-cli version 2>/dev/null || true
}

ensure_gemini_cli_latest() {
  if ! command -v npm >/dev/null 2>&1; then
    log "ERROR - npm is not installed. Please install Node.js & npm."
    exit 1
  fi

  local installed latest newest
  installed="$(installed_gemini_version)"
  latest="$(latest_gemini_version)"

  if [[ -z "$installed" ]]; then
    log "'gemini' CLI not found. Installing @google/gemini-cli@latest..."
    (cd "$PROJECT_ROOT" && npm install)
    return
  fi

  if [[ -z "$latest" ]]; then
    log "Installed gemini-cli v$installed; unable to check latest. Continuing."
    return
  fi

  newest="$(printf '%s\n%s\n' "$installed" "$latest" | sort -V | tail -n1)"
  if [[ "$newest" != "$installed" ]]; then
    log "Update available: gemini-cli $installed -> $latest. Installing latest…"
    (cd "$PROJECT_ROOT" && npm install)
  else
    log "gemini-cli is up to date (v$installed)."
  fi
}

# --- Args ---

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <task_id> [mode]"
  echo "Example: $0 task-20250728-alpha interactive"
  exit 1
fi

TASK_ID="$1"
MODE="${2:-interactive}"

echo "--- LAUNCHER: Initializing Task [$TASK_ID] in [$MODE] mode ---"

# --- Load env ---

CONFIG_PATH="$SCRIPT_DIR/config/.env"
if [[ -f "$CONFIG_PATH" ]]; then
  log "Loading environment from $CONFIG_PATH"
  set -a
  # shellcheck disable=SC1090
  . "$CONFIG_PATH"
  set +a
else
  log "Warning - Configuration file not found at $CONFIG_PATH"
fi

# Ensure libpq sees credentials even if DSN omits them
export PGHOST="${PGHOST:-localhost}"
export PGPORT="${PGPORT:-5432}"
export PGDATABASE="${PGDATABASE:-gemini_agents}"
export PGUSER="${PGUSER:-gemini_user}"
export PGPASSWORD="${PGPASSWORD:-}"
export DATABASE_URL="${DATABASE_URL:-}"

# --- Select API key ---

log "Selecting API key…"

# Prefer /srv/gemini/venv, then .venv, then system python
PY_BIN="$PROJECT_ROOT/venv/bin/python"
[[ -x "$PY_BIN" ]] || PY_BIN="$PROJECT_ROOT/.venv/bin/python"
[[ -x "$PY_BIN" ]] || PY_BIN="python3"

eval "$($PY_BIN "$SCRIPT_DIR/scripts/select_key.py" --mark-use --reserve 10 --format env)"
export GEMINI_API_KEY
log "Using key $(mask_key "$GEMINI_API_KEY") (name: $KEY_NAME) via $(basename "$PY_BIN")"

# --- (Optional) Context populate hook ---

log "Populating context…"
# "$PY_BIN" "$SCRIPT_DIR/scripts/populate_context.py" --task_id "$TASK_ID"


# --- Ensure gemini CLI exists & is latest ---
ensure_gemini_cli_latest

# --- Run CLI ---

log "Starting Gemini CLI."
echo "---------------------------------------------------------------------"
cd /

case $MODE in
    headless)
        read -p "Enter your prompt: " prompt
        "$GEMINI_CLI" --prompt "$prompt"
        ;;
    context)
        "$GEMINI_CLI" --all-files
        ;;
    agentic)
        read -p "Enter your prompt for the agent to execute: " prompt
        "$GEMINI_CLI" --prompt "$prompt" --yolo
        ;;
    *)
        "$GEMINI_CLI"
        ;;
esac

echo "---------------------------------------------------------------------"
log "Gemini CLI session ended."

# --- Post-session hook ---

log "Tracking API usage…"
"$PY_BIN" "$SCRIPT_DIR/scripts/track_api_usage.py" --key-name "$KEY_NAME"

log "Logging session details to database…"
# "$PY_BIN" "$SCRIPT_DIR/scripts/log_session.py" --task_id "$TASK_ID"
log "(Skipped - log_session.py not implemented)"

echo "--- LAUNCHER: Task [$TASK_ID] finished ---"