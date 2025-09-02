import os
import sys
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

# Quota limits from GEMINI.md (using the lower, safer limit for general use)
DAILY_REQUEST_LIMIT = 960

def _connect():
    try:
        return psycopg2.connect(
            dbname=DB_NAME, user=DB_USER, password=DB_PASS,
            host=DB_HOST, port=DB_PORT
        )
    except Exception as e:
        print(f"[track_api_usage] DB connect failed: {e}", file=sys.stderr)
        sys.exit(1)

def track_usage(key_name):
    conn = _connect()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            # Get current daily_request_count
            cur.execute(
                "SELECT daily_request_count FROM api_keys WHERE key_name = %s;",
                (key_name,)
            )
            result = cur.fetchone()
            if not result:
                print(f"[track_api_usage] Key '{key_name}' not found in api_keys table.", file=sys.stderr)
                return

            current_count = result["daily_request_count"] if result["daily_request_count"] is not None else 0
            new_count = current_count + 1

            # Update daily_request_count and check for quota exhaustion
            quota_exhausted = False
            if new_count >= DAILY_REQUEST_LIMIT:
                quota_exhausted = True

            cur.execute(
                "UPDATE api_keys SET daily_request_count = %s, quota_exhausted = %s WHERE key_name = %s;",
                (new_count, quota_exhausted, key_name)
            )
            conn.commit()
            print(f"[track_api_usage] Key '{key_name}': daily_request_count updated to {new_count}. Quota exhausted: {quota_exhausted}.", file=sys.stderr)

    except Exception as e:
        print(f"[track_api_usage] Error tracking usage for key '{key_name}': {e}", file=sys.stderr)
    finally:
        conn.close()

def main():
    parser = argparse.ArgumentParser(description="Track API key usage and update quota status.")
    parser.add_argument("--key-name", required=True, help="The name of the API key used.")
    args = parser.parse_args()

    track_usage(args.key_name)

if __name__ == "__main__":
    main()
