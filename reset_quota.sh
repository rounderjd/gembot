#!/bin/bash

# This script resets the daily quota for all API keys in the database.
# It should be run once a day via a cron job.

# Get the directory of the script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Source the main .env file to get the path to the credentials
if [ -f "$SCRIPT_DIR/.env" ]; then
  source "$SCRIPT_DIR/.env"
else
  echo "Error: Main .env file not found."
  exit 1
fi

# Source the PostgreSQL credentials
if [ -f "$POSTGRES_ENV_FILE" ]; then
  source "$POSTGRES_ENV_FILE"
else
  echo "Error: PostgreSQL .env file not found at $POSTGRES_ENV_FILE."
  exit 1
fi

# --- Database Connection Details ---
export PGPASSWORD=$POSTGRES_PASSWORD
DB_NAME=$POSTGRES_DB
DB_USER=$POSTGRES_USER
DB_HOST=$POSTGRES_HOST

# --- SQL Command ---
SQL_COMMAND="UPDATE api_keys SET daily_token_total = 0, daily_request_count = 0, quota_exhausted = FALSE, disabled_until = NULL;"

# --- Execute Command ---
psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -c "$SQL_COMMAND"

echo "Daily quota reset complete."
