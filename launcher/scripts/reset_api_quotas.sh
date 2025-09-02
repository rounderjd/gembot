#!/bin/bash

# Load environment variables
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)
PROJECT_ROOT=$(cd -- "$SCRIPT_DIR/.." &>/dev/null && pwd)
ENV_FILE="$PROJECT_ROOT/.postgres.env"

if [[ -f "$ENV_FILE" ]]; then
  source "$ENV_FILE"
else
  echo "Error: .postgres.env not found at $ENV_FILE"
  exit 1
fi

# Set default values if not present in .postgres.env
PGHOST="${POSTGRES_HOST:-localhost}"
PGPORT="${POSTGRES_PORT:-5432}"
PGDATABASE="${POSTGRES_DB:-gemini_agents}"
PGUSER="${POSTGRES_USER:-gemini_user}"
PGPASSWORD="${POSTGRES_PASSWORD:-}"

# Export for psql
export PGPASSWORD

# Execute the SQL command
psql -h "$PGHOST" -p "$PGPORT" -d "$PGDATABASE" -U "$PGUSER" -c "UPDATE api_keys SET daily_request_count = 0, quota_exhausted = FALSE;"

if [ $? -eq 0 ]; then
  echo "$(date): API quotas reset successfully."
else
  echo "$(date): Error resetting API quotas." >&2
fi
