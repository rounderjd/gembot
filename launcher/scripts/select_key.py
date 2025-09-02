#!/usr/bin/env python3
"""
select_key.py — pick a usable API key from the database safely.

- Loads DB creds from .postgres.env (POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_PORT)
- Chooses ONE available key from api_keys:
    * NOT quota_exhausted (or NULL)
    * disabled_until IS NULL or <= NOW()
  Ordered by: lowest daily_request_count, then daily_token_total, then oldest last_used.

- Transaction-safe: uses SELECT ... FOR UPDATE SKIP LOCKED to avoid races across multiple callers.

- Outputs in one of:
    * plain (default): just the API key value
    * env:  two lines   KEY_NAME=... and GEMINI_API_KEY=...
    * json: {"key_name":"...", "api_key":"..."}

- Options:
    --mark-use          increment daily_request_count and set last_used=NOW()
    --reserve SECONDS   sets disabled_until=NOW()+SECONDS (soft-reserve the key)
    --format {plain,env,json}
    --service NAME      ignored by default (reserved for multi-service tables)
    --require-enabled   fail if key.quota_exhausted is true (default behavior)
    --allow-exhausted   ignore quota_exhausted and still select unlocked keys
    --verbose

Exit codes:
    0 = success
    2 = no available key
    3 = schema missing or no secret column found
    4 = database error
"""

import os
import sys
import json
import argparse
import datetime as dt
import psycopg2
from psycopg2.extras import DictCursor
from dotenv import load_dotenv

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
dotenv_path = os.path.join(ROOT, ".postgres.env")
load_dotenv(dotenv_path=dotenv_path)

DB_NAME = os.getenv("POSTGRES_DB")
DB_USER = os.getenv("POSTGRES_USER")
DB_PASS = os.getenv("POSTGRES_PASSWORD")
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = int(os.getenv("POSTGRES_PORT", "5432"))


def _connect():
    try:
        return psycopg2.connect(
            dbname=DB_NAME, user=DB_USER, password=DB_PASS,
            host=DB_HOST, port=DB_PORT
        )
    except Exception as e:
        print(f"[select_key] DB connect failed: {e}", file=sys.stderr)
        sys.exit(4)


def _col_exists(cur, table, column):
    cur.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_name=%s AND column_name=%s
        """,
        (table, column),
    )
    return cur.fetchone() is not None


def _detect_secret_column(cur):
    """
    Determine which column stores the API secret:
    try 'api_key', then 'key_value', then 'key'.
    """
    for col in ("api_key", "key_value", "key"):
        if _col_exists(cur, "api_keys", col):
            return col
    return None


def _detect_optional_columns(cur):
    """Return a dict of column->bool for columns we use if present."""
    names = [
        "key_name", "daily_request_count", "daily_token_total", "last_used",
        "quota_exhausted", "disabled_until", "service_name", "tags"
    ]
    have = {}
    for n in names:
        have[n] = _col_exists(cur, "api_keys", n)
    return have


def select_key(conn, allow_exhausted=False, reserve_seconds=None, mark_use=False, service=None, verbose=False):
    with conn.cursor(cursor_factory=DictCursor) as cur:
        # Build the WHERE clause
        where_clauses = []
        if not allow_exhausted:
            where_clauses.append("(quota_exhausted = FALSE OR quota_exhausted IS NULL)")
        where_clauses.append("(disabled_until IS NULL OR disabled_until < NOW())")

        where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        # Build the ORDER BY clause
        order_sql = "ORDER BY daily_request_count ASC, daily_token_total ASC, last_used ASC NULLS FIRST"

        # Detect the secret column name
        secret_col = _detect_secret_column(cur)
        if not secret_col:
            print("[select_key] No secret column found in api_keys table.", file=sys.stderr)
            sys.exit(3)

        # Detect optional columns
        have_cols = _detect_optional_columns(cur)

        # Build the SELECT statement
        select_cols = ["key_name", secret_col]
        if have_cols["daily_request_count"]: select_cols.append("daily_request_count")
        if have_cols["daily_token_total"]: select_cols.append("daily_token_total")
        if have_cols["last_used"]: select_cols.append("last_used")
        if have_cols["quota_exhausted"]: select_cols.append("quota_exhausted")
        if have_cols["disabled_until"]: select_cols.append("disabled_until")
        if have_cols["service_name"]: select_cols.append("service_name")
        if have_cols["tags"]: select_cols.append("tags")

        select_sql = f"SELECT {', '.join(select_cols)} FROM api_keys {where_sql} {order_sql} FOR UPDATE SKIP LOCKED LIMIT 1;"

        cur.execute(select_sql)
        key_info = cur.fetchone()

        if not key_info:
            return None, None # No available key

        key_name = key_info["key_name"] if "key_name" in key_info else None
        api_key = key_info[secret_col]

        # Apply mark_use and reserve if requested
        if mark_use or reserve_seconds:
            update_clauses = []
            if mark_use:
                update_clauses.append("daily_request_count = COALESCE(daily_request_count, 0) + 1")
                update_clauses.append("last_used = NOW()")
            if reserve_seconds:
                update_clauses.append(f"disabled_until = NOW() + INTERVAL '{reserve_seconds} seconds'")

            if update_clauses:
                update_sql = f"UPDATE api_keys SET {', '.join(update_clauses)} WHERE key_name = %s;"
                cur.execute(update_sql, (key_name,))
                conn.commit()

        return key_name, api_key


def main():
    ap = argparse.ArgumentParser(description="Select a usable API key from the database.")
    ap.add_argument("--format", choices=["plain", "env", "json"], default="plain",
                    help="Output format. 'plain' prints only the API key (default).")
    ap.add_argument("--mark-use", action="store_true",
                    help="Increment daily_request_count and set last_used=NOW().")
    ap.add_argument("--reserve", type=int, default=0, metavar="SECONDS",
                    help="Soft-reserve the key by setting disabled_until=NOW()+SECONDS.")
    ap.add_argument("--allow-exhausted", action="store_true",
                    help="Ignore quota_exhausted and still select keys (default: false).")
    ap.add_argument("--service", default=None,
                    help="Optional service filter if api_keys.service_name exists.")
    ap.add_argument("--verbose", action="store_true", help="Verbose logging to stderr.")
    args = ap.parse_args()

    conn = _connect()
    try:
        key_name, api_key = select_key(
            conn,
            allow_exhausted=args.allow_exhausted,
            reserve_seconds=args.reserve if args.reserve > 0 else None,
            mark_use=args.mark_use,
            service=args.service,
            verbose=args.verbose,
        )
    except psycopg2.errors.UndefinedTable:
        print("[select_key] Table 'api_keys' does not exist. Create it first.", file=sys.stderr)
        sys.exit(3)
    except Exception as e:
        print(f"[select_key] DB error: {e}", file=sys.stderr)
        sys.exit(4)
    finally:
        conn.close()

    if not api_key:
        if args.verbose:
            print("[select_key] No available key.", file=sys.stderr)
        sys.exit(2)

    if args.format == "plain":
        print(api_key)
    elif args.format == "env":
        # keep names predictable for your wrappers
        print(f"KEY_NAME={key_name or ''}")
        print(f"GEMINI_API_KEY={api_key}")
    else:  # json
        print(json.dumps({"key_name": key_name, "api_key": api_key}))
    sys.exit(0)


if __name__ == "__main__":
    main()
