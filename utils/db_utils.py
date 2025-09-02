

import psycopg2
import logging
import json
import datetime
import socket
import os
import time
import redis
from dotenv import load_dotenv

# --- Configuration ---
# Load the main .env file to get the root paths
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path=dotenv_path)

# Load the PostgreSQL credentials from the path specified in the main .env file
postgres_env_path = os.getenv("POSTGRES_ENV_FILE")
if postgres_env_path and os.path.exists(postgres_env_path):
    load_dotenv(dotenv_path=postgres_env_path, override=True)
else:
    logging.warning(f"POSTGRES_ENV_FILE is not set or the file does not exist: {postgres_env_path}")

# Use the correct database name discovered from the docker container
DB_NAME = os.getenv("POSTGRES_DB", "speedtesttracker") 
DB_USER = os.getenv("POSTGRES_USER", "rootuser")
DB_PASS = os.getenv("POSTGRES_PASSWORD")
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
MIN_REQUEST_INTERVAL_SECONDS = 30

# Redis Configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_KEY_LIST = "available_api_keys"

def get_redis_connection():
    """Establishes a connection to the Redis server."""
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
        r.ping()
        logging.info("Successfully connected to Redis.")
        return r
    except redis.exceptions.ConnectionError as e:
        logging.error(f"Redis connection failed: {e}")
        return None

def get_db_connection():
    """Establishes a connection to the PostgreSQL database."""
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST, port=DB_PORT
        )
        return conn
    except psycopg2.OperationalError as e:
        logging.error(f"Database connection failed: {e}")
        return None

def get_task_id():
    """Generates a unique task ID from the hostname and current date."""
    hostname = socket.gethostname()
    today = datetime.date.today().strftime('%Y-%m-%d')
    import uuid
    return f"{hostname}-{today}-{{str(uuid.uuid4())[:8]}}" 

def get_or_create_task(cur, task_id):
    """Fetches a task by ID or creates a new one if it doesn't exist."""
    cur.execute("SELECT id FROM tasks WHERE id = %s;", (task_id,))
    task = cur.fetchone()
    if task:
        logging.info(f"Resuming existing task: {task_id}")
    else:
        logging.info(f"Creating new task: {task_id}")
        cur.execute(
            "INSERT INTO tasks (id, status) VALUES (%s, %s);",
            (task_id, 'active')
        )
    return {'history': get_task_history(cur, task_id)}

def get_task_history(cur, task_id):
    """Retrieves the full conversation history for a task."""
    history = []
    cur.execute(
        "SELECT prompt, response FROM interactions WHERE task_id = %s ORDER BY request_timestamp ASC;",
        (task_id,)
    )
    for row in cur.fetchall():
        history.append({'prompt': row[0], 'response': row[1]})
    return history

def add_interaction_to_history(cur, task_id, prompt, response):
    """Adds a new prompt-response pair to the interactions table."""
    cur.execute(
        "INSERT INTO interactions (task_id, prompt, response) VALUES (%s, %s, %s);",
        (task_id, prompt, response)
    )
    cur.execute(
        "UPDATE tasks SET last_updated = NOW() WHERE id = %s;",
        (task_id,)
    )
    logging.info(f"Added new interaction for task '{task_id}' to database.")

def log_command(cur, task_id, prompt, command, thought, parent_command_id=None, permissions="superuser", user_confirmation=False, agent_mode="ReAct"):
    """Logs a command and its preceding thought to the command_log table."""
    cur.execute("""
        INSERT INTO command_log (task_id, prompt, command, thought, parent_command_id, permissions, user_confirmation, agent_mode, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pending_confirmation') RETURNING id;
    """, (task_id, prompt, command, thought, parent_command_id, permissions, user_confirmation, agent_mode))
    return cur.fetchone()[0]

def log_command_output(cur, command_log_id, stdout, stderr, return_code, file_written, success):
    """Logs the output of a command and updates the observation field."""
    # First, log to the dedicated output table
    cur.execute("""
        INSERT INTO command_output (command_log_id, stdout, stderr, return_code, file_written, success)
        VALUES (%s, %s, %s, %s, %s, %s);
    """, (command_log_id, stdout, stderr, return_code, file_written, success))
    
    # Second, update the observation field in the main command_log table
    observation = f"STDOUT:\n{stdout}\n\nSTDERR:\n{stderr}"
    cur.execute("""
        UPDATE command_log SET observation = %s WHERE id = %s;
    """, (observation, command_log_id))


def store_project_file(cur, task_id, path, content):
    """Stores or updates a project file in the project_files table."""
    cur.execute("""
        INSERT INTO project_files (task_id, path, content, last_updated)
        VALUES (%s, %s, %s, NOW())
        ON CONFLICT (task_id, path) DO UPDATE SET content = EXCLUDED.content, last_updated = NOW();
    """, (task_id, path, content))

def store_knowledge(cur, task_id, fact_label, fact_value, extracted_from, confidence_score):
    """Stores a new fact in the knowledge table."""
    cur.execute("""
        INSERT INTO knowledge (task_id, fact_label, fact_value, extracted_from, confidence_score)
        VALUES (%s, %s, %s, %s, %s);
    """, (task_id, fact_label, fact_value, extracted_from, confidence_score))

def get_available_key(cur, redis_conn):
    """Retrieves an available API key, using Redis as a cache."""
    if redis_conn:
        key_json = redis_conn.lpop(REDIS_KEY_LIST)
        if key_json:
            key_info = json.loads(key_json)
            logging.info(f"Retrieved key ID {key_info['id']} from Redis cache.")
            return key_info['id'], key_info['value']

    logging.warning("Redis cache miss or connection failed. Querying database for keys.")
    cur.execute("""
        SELECT id, key_value
        FROM api_keys
        WHERE (quota_exhausted = FALSE OR quota_exhausted IS NULL)
          AND (disabled_until IS NULL OR disabled_until < NOW())
          AND daily_request_count < 60
        ORDER BY last_used ASC NULLS FIRST;
    """)
    keys = cur.fetchall()
    
    if not keys:
        return None

    if redis_conn:
        redis_conn.delete(REDIS_KEY_LIST)
        pipe = redis_conn.pipeline()
        for key_id, key_value in keys:
            key_info = json.dumps({'id': key_id, 'value': key_value})
            pipe.rpush(REDIS_KEY_LIST, key_info)
        pipe.execute()
        logging.info(f"Refreshed Redis cache with {len(keys)} available keys.")
        key_json = redis_conn.lpop(REDIS_KEY_LIST)
        if key_json:
            key_info = json.loads(key_json)
            return key_info['id'], key_info['value']

    return keys[0]


def release_key(key_id):
    """Updates the last_used timestamp for a key, making it available again."""
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            logging.error("Could not get database connection to release key.")
            return
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE api_keys
                SET last_used = NOW()
                WHERE id = %s;
            """, (key_id,))
            conn.commit()
            logging.info(f"Successfully released API key ID {key_id}.")
    except Exception as e:
        logging.error(f"Failed to release key ID {key_id}: {e}")
    finally:
        if conn:
            conn.close()


def throttle_if_needed(cur, key_name):
    """Sleeps if the key was used too recently to avoid rate limits."""
    cur.execute("SELECT last_used FROM api_keys WHERE key_name = %s;", (key_name,))
    last_used = cur.fetchone()[0]
    
    if last_used:
        if last_used.tzinfo is None:
            last_used = last_used.replace(tzinfo=datetime.timezone.utc)
            
        time_since_last_use = (datetime.datetime.now(datetime.timezone.utc) - last_used).total_seconds()
        if time_since_last_use < MIN_REQUEST_INTERVAL_SECONDS:
            sleep_time = MIN_REQUEST_INTERVAL_SECONDS - time_since_last_use
            logging.info(f"Throttling: key '{key_name}' used {time_since_last_use:.1f}s ago. Sleeping for {sleep_time:.1f}s.")
            time.sleep(sleep_time)

def update_key_and_log_usage(cur, key_name, task_id, token_count, request_type):
    """Updates key stats and logs the request."""
    cur.execute("""
        UPDATE api_keys
        SET last_used = NOW(),
            daily_request_count = daily_request_count + 1,
            daily_token_total = daily_token_total + %s
        WHERE key_name = %s;
    """, (token_count, key_name))

    cur.execute("""
        INSERT INTO usage_log (key_name, task_id, token_count, request_type)
        VALUES (%s, %s, %s, %s);
    """, (key_name, task_id, token_count, request_type))
    logging.info(f"Updated usage for key '{key_name}' in database.")

def check_and_notify_quota_usage(cur, key_name, threshold=55):
    """Checks the daily request count for a key and sends a Slack notification."""
    cur.execute("SELECT daily_request_count FROM api_keys WHERE key_name = %s;", (key_name,))
    count = cur.fetchone()[0]

    if count == threshold:
        message = f"API key '{key_name}' is nearing its daily quota, having made {count} requests."
        send_slack_notification(message, level="warning")
        logging.warning(message)
    elif count >= 60:
        message = f"API key '{key_name}' has reached its daily quota with {count} requests."
        send_slack_notification(message, level="error")
        logging.warning(message)
        redis_conn = get_redis_connection()
        if redis_conn:
            redis_conn.delete(REDIS_KEY_LIST)
            logging.info("Cleared Redis key cache because a key reached its quota.")

def send_slack_notification(message, channel=None, pretext=None, level="info"):
    """Sends a notification to a Slack webhook."""
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook_url or webhook_url == "https://hooks.slack.com/services/YOUR/WEBHOOK/URL":
        logging.warning("Slack webhook URL not configured. Skipping notification.")
        return

    color = {
        "info": "#36a64f",
        "warning": "#ffae42",
        "error": "#d50200"
    }.get(level, "#cccccc")

    payload = {
        "attachments": [
            {
                "color": color,
                "pretext": pretext,
                "text": message,
                "ts": datetime.datetime.now().timestamp()
            }
        ]
    }
    
    if channel:
        payload['channel'] = channel

    try:
        import requests
        response = requests.post(webhook_url, json=payload)
        if response.status_code != 200:
            logging.warning(f"Failed to send Slack notification. Status: {response.status_code}, Response: {response.text}")
    except Exception as e:
        logging.error(f"Exception while sending Slack notification: {e}", exc_info=True)


def log_cli_command(cur, task_id, prompt, command, approved, agentic, permissions="superuser"):
    """
    Minimal, schema-accurate insert for CLI runs.
    - approved: bool -> user_confirmation
    - agentic: bool -> agent_mode "Agentic"/"Interactive"
    - permissions: text (e.g., "superuser")
    Returns new command_log id.
    """
    agent_mode = "Agentic" if agentic else "Interactive"
    cur.execute("""
        INSERT INTO command_log
            (task_id, prompt, command, permissions, user_confirmation, agent_mode, status)
        VALUES
            (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id;
    """, (task_id, prompt, command, permissions, approved, agent_mode, 'queued'))
    new_id = cur.fetchone()[0]
    cur.connection.commit()
    return new_id
