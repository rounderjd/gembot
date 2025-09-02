#!/usr/bin/env python3
import os, sys, subprocess, argparse, logging, datetime, hashlib, readline, shutil, re

AGENT_DIR = os.path.dirname(__file__)
sys.path.append(AGENT_DIR)
try:
    from utils import db_utils
except ImportError as e:
    sys.exit(f"Fatal Error: Could not from utils import db_utils.py. Details: {e}")

COMMAND_TIMEOUT = 300
# Prefer env, PATH, then best match under ~/.nvm
NVM_DIR = os.environ.get("NVM_DIR", os.path.expanduser("~/.nvm"))
HISTFILE = os.path.expanduser("~/.gemini_history")
LOG_FILE = os.path.join(AGENT_DIR, "interactive_wrapper.log")
USER_ID = int(os.environ.get("GEMMA_USER_ID", "1"))  # kept for future use
PERMISSIONS = os.environ.get("GEMMA_PERMISSIONS", "superuser")

PROMPT_PREFIX = (
    "You are a command-only assistant. "
    "Return ONLY one single POSIX shell command on one line. "
    "Do NOT include backticks, code fences, explanations, or comments. "
    "If the request is not about shell operations, return exactly: echo UNSUPPORTED"
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s",
                    handlers=[logging.FileHandler(LOG_FILE)])

def find_gemini_exec() -> str:
    # 1) explicit env
    env_exec = os.environ.get("GEMINI_EXEC")
    if env_exec and os.path.isfile(env_exec) and os.access(env_exec, os.X_OK):
        return env_exec

    # 2) PATH
    which = shutil.which("gemini")
    if which:
        return which

    # 3) look for latest under NVM
    versions_dir = os.path.join(NVM_DIR, "versions", "node")
    if os.path.isdir(versions_dir):
        candidates = []
        for v in sorted(os.listdir(versions_dir), reverse=True):
            p = os.path.join(versions_dir, v, "bin", "gemini")
            if os.path.isfile(p) and os.access(p, os.X_OK):
                candidates.append(p)
        if candidates:
            return candidates[0]

    sys.exit("Fatal Error: Could not find `gemini` CLI. Install it, or set GEMINI_EXEC, or install via NVM.")

def generate_task_id(prompt: str) -> str:
    hostname = os.uname().nodename
    timestamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    prompt_hash = hashlib.md5(prompt.encode()).hexdigest()[:8]
    return f"interactive-{hostname}-{timestamp}-{prompt_hash}"

def sanitize_command(text: str) -> str:
    if not text: return "echo UNSUPPORTED"
    m = re.search(r"```(?:sh|bash)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if m: text = m.group(1)
    line = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
    line = re.sub(r"^[$]\s*", "", line).strip().strip("`")
    if not line or re.search(r"\b(can.?t|cannot|sorry|unable|I am|I\'m)\b", line, re.IGNORECASE):
        return "echo UNSUPPORTED"
    return line.splitlines()[0].strip() or "echo UNSUPPORTED"

def get_command_from_gemini(user_prompt: str, key_name: str, api_key: str, gemini_exec: str) -> str | None:
    logging.info(f"Getting command from Gemini for key {key_name}")
    env = os.environ.copy()
    env["GEMINI_API_KEY"] = api_key
    gem_dir = os.path.dirname(gemini_exec)
    env["PATH"] = f"{gem_dir}:{env.get('PATH','')}"
    final_prompt = f"{PROMPT_PREFIX}\n\nUser request: {user_prompt}"
    try:
        result = subprocess.run([gemini_exec], input=final_prompt, capture_output=True,
                                text=True, env=env, timeout=COMMAND_TIMEOUT)
        if result.returncode == 0:
            return sanitize_command(result.stdout)
        logging.error(f"Gemini CLI failed. Stderr: {result.stderr.strip()}")
        return None
    except subprocess.TimeoutExpired:
        logging.error("Gemini CLI timed out while generating command.")
        return None

def execute_and_stream_command(cur, command_log_id: int, command_to_run: str, gemini_exec: str):
    logging.info(f"Executing confirmed command (Log ID: {command_log_id})")
    env = os.environ.copy()
    gem_dir = os.path.dirname(gemini_exec)
    env["PATH"] = f"{gem_dir}:{env.get('PATH','')}"
    full_stdout, full_stderr = [], []
    success, returncode = False, -1
    try:
        try:
            cur.execute("UPDATE command_log SET status='running', command_start_timestamp=NOW() WHERE id=%s;", (command_log_id,))
            cur.connection.commit()
        except Exception:
            pass
        process = subprocess.Popen(command_to_run, shell=True, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True, env=env)
        for line in iter(process.stdout.readline, ''):
            print(line, end=''); full_stdout.append(line)
        stderr_lines = process.stderr.readlines(); full_stderr.extend(stderr_lines)
        returncode = process.wait(timeout=COMMAND_TIMEOUT)
        success = (returncode == 0)
    except subprocess.TimeoutExpired:
        full_stderr.append(f"Command timed out after {COMMAND_TIMEOUT} seconds.")
        logging.error(full_stderr[-1])
    stdout_str = "".join(full_stdout)
    stderr_str = "".join(full_stderr).strip()
    db_utils.log_command_output(cur, command_log_id, stdout_str, stderr_str, returncode, None, success)
    try:
        cur.execute("UPDATE command_log SET status=%s, command_end_timestamp=NOW() WHERE id=%s;",
                    ('completed' if success else 'failed', command_log_id))
        cur.connection.commit()
    except Exception:
        pass

def process_interactive_prompt(cur, task_id: str, prompt: str, key_name: str, api_key: str,
                               is_agentic: bool, auto_approve: bool, gemini_exec: str):
    original_prompt = prompt
    while True:
        print("[Agent] Getting command from Gemini...")
        command_to_run = get_command_from_gemini(prompt, key_name, api_key, gemini_exec)
        if not command_to_run:
            print("[Agent] Could not get a command from Gemini. Please try again.", file=sys.stderr)
            return
        if command_to_run.strip() == "echo UNSUPPORTED":
            print("[Agent] Model could not produce a shell command. Try rephrasing.")
            return

        if is_agentic or auto_approve:
            mode = "agentic" if is_agentic else "auto-approve"
            print(f"[Agent] Running command in {mode} mode:\n  {command_to_run}")
            command_log_id = db_utils.log_cli_command(cur, task_id, original_prompt,
                                                      command_to_run, approved=True,
                                                      agentic=is_agentic, permissions=PERMISSIONS)
            print("[Agent] Logged command_log_id =", command_log_id)
            execute_and_stream_command(cur, command_log_id, command_to_run, gemini_exec)
            break

        print(f"\n[Agent] The following command was generated:\n  {command_to_run}")
        try:
            user_input = input("> Approve? [y/n/edit]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            user_input = 'n'

        if user_input == 'y':
            command_log_id = db_utils.log_cli_command(cur, task_id, original_prompt,
                                                      command_to_run, approved=True,
                                                      agentic=False, permissions=PERMISSIONS)
            print("[Agent] Logged command_log_id =", command_log_id)
            execute_and_stream_command(cur, command_log_id, command_to_run, gemini_exec)
            break
        elif user_input == 'n':
            print("[Agent] Command execution denied.")
            command_log_id = db_utils.log_cli_command(cur, task_id, original_prompt,
                                                      command_to_run, approved=False,
                                                      agentic=False, permissions=PERMISSIONS)
            print("[Agent] Logged command_log_id =", command_log_id)
            break
        else:
            print("[Agent] Treating input as an edited prompt.")
            prompt = user_input

def load_history():
    try: readline.read_history_file(HISTFILE)
    except FileNotFoundError: pass
    readline.set_history_length(1000)

def save_history():
    try: readline.write_history_file(HISTFILE)
    except Exception: pass

def start_interactive_session(conn, redis_conn, is_agentic: bool, auto_approve: bool):
    mode = "Agentic" if is_agentic else ("Interactive (auto-approve)" if auto_approve else "Interactive")
    print(f"Starting {mode} Gemini session. Type 'exit' or 'quit' to end.")
    logging.info(f"Starting {mode} session.")
    gemini_exec = find_gemini_exec()
    load_history()
    try:
        with conn.cursor() as cur:
            key_info = db_utils.get_available_key(cur, redis_conn)
            if not key_info:
                sys.exit("Error: No available API keys. Please check the database.")
            key_name, api_key = key_info
            print(f"Using API Key: {key_name}")
            session_task_id = generate_task_id("interactive-session")
            db_utils.get_or_create_task(cur, session_task_id)
            conn.commit()
            while True:
                try:
                    prompt = input("gemini> ").strip()
                    if not prompt: continue
                    if prompt.lower() in ['exit','quit']: break
                    db_utils.throttle_if_needed(cur, key_name)
                    process_interactive_prompt(cur, session_task_id, prompt, key_name, api_key,
                                               is_agentic, auto_approve, gemini_exec)
                except (EOFError, KeyboardInterrupt):
                    break
    finally:
        save_history()
        print("\nExiting session.")
        logging.info("Session ended.")

def main():
    parser = argparse.ArgumentParser(description="Gemini Interactive Wrapper with DB Logging, key mgmt, and agentic mode")
    parser.add_argument('--agentic', action='store_true', help="Bypass confirmation prompts and run the returned command.")
    parser.add_argument('--auto-approve', action='store_true', help="Approve without asking (still interactive prompt loop).")
    args = parser.parse_args()
    conn = db_utils.get_db_connection()
    if not conn:
        sys.exit("Fatal Error: Could not connect to the database.")
    redis_conn = db_utils.get_redis_connection()
    try:
        start_interactive_session(conn, redis_conn, is_agentic=args.agentic, auto_approve=args.auto_approve)
    finally:
        if conn: conn.close()

if __name__ == "__main__":
    main()
