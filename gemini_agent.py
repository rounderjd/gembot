import os
from dotenv import load_dotenv

# --- Pre-emptive Environment Loading ---
# Load environment variables from .env file before anything else.
# This ensures that all configurations, especially for logging, are available.
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(dotenv_path) and os.access(dotenv_path, os.R_OK):
    try:
        load_dotenv(dotenv_path=dotenv_path, override=True)
        print(f"Successfully loaded .env file from {dotenv_path}")
    except Exception as e:
        print(f"Error loading .env file: {e}")
else:
    print(f"Warning: .env file not found at {dotenv_path} or is not readable. Proceeding with environment variables or defaults.")

from utils import db_utils
import time
import logging
import subprocess
import json
import sys
import argparse
import re
import threading
import itertools

# --- Configuration ---
# Now, access the environment variables after they've been loaded.
PROJECT_ROOT = os.getenv("GEMINI_AGENT_ROOT", os.path.dirname(__file__))
# Ensure the log file is always created in the script's directory, which should be writable.
LOG_FILE = os.path.join(os.path.dirname(__file__), "agent.log")
KEY_EXHAUSTED_SLEEP_MINUTES = 5

# --- Global Permissions ---
# Load permissions from config at a global scope so all functions can access them.
try:
    with open('agent_config.json', 'r') as f:
        config = json.load(f)
    WEAK_ALLOWED_COMMANDS = config.get('permissions', {}).get('weak', {}).get('allowlist', [])
    SUPERUSER_DENIED_COMMANDS = config.get('permissions', {}).get('superuser', {}).get('denylist', [])
except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
    logging.error(f"Failed to load permissions from agent_config.json: {e}. Defaulting to empty lists.")
    WEAK_ALLOWED_COMMANDS = []
    SUPERUSER_DENIED_COMMANDS = []

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

# --- UX Enhancements ---
class Spinner:
    """A simple spinner class to show activity."""
    def __init__(self, message="Thinking..."):
        self.spinner = itertools.cycle(['-', '/', '|', '\\'])
        self.message = message
        self.running = False
        self.thread = None

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._spin)
        self.thread.start()

    def stop(self):
        if self.thread and self.running:
            self.running = False
            self.thread.join()
            # Clear the spinner line
            sys.stdout.write('\r' + ' ' * (len(self.message) + 2) + '\r')
            sys.stdout.flush()

    def _spin(self):
        while self.running:
            sys.stdout.write('\r' + self.message + ' ' + next(self.spinner))
            sys.stdout.flush()
            time.sleep(0.1)

class RateLimitException(Exception):
    """Custom exception for 429 rate limit errors."""
    pass

def run_gemini_command(api_key, prompt, context_history, base_context=None):

    """
    Runs the Gemini CLI with the provided API key, prompt, and context.
    """
    logging.info(f"Executing Gemini command with key ending in '...{api_key[-4:]}'")
    
    cmd = ["gemini"]
    
    # Construct the full prompt with history and base context
    full_prompt = ""
    if base_context:
        full_prompt += "--- Start of Base Context ---\n"
        full_prompt += json.dumps(base_context, indent=2)
        full_prompt += "\n--- End of Base Context ---\n\n"

    for interaction in context_history:
        full_prompt += f"Previous Prompt: {interaction['prompt']}\n"
        full_prompt += f"Previous Response: {interaction['response']}\n\n"
    full_prompt += f"Current Prompt: {prompt}"
    full_prompt += "\n\nImportant: Your response must contain only a single, valid shell command enclosed in a ```bash code block. Do not include any other text, explanations, or formatting."

    spinner = Spinner("Communicating with Gemini...")
    spinner.start()
    try:
        env = os.environ.copy()
        env["GEMINI_API_KEY"] = api_key
        
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            check=True, 
            env=env,
            input=full_prompt
        )
        
        spinner.stop()
        response = result.stdout.strip()
        token_count = len(full_prompt.split()) + len(response.split())

        logging.info(f"Gemini command successful. Response: {response}, Token usage: {token_count}")
        return response, token_count

    except subprocess.CalledProcessError as e:
        spinner.stop()
        stderr = e.stderr.lower() if e.stderr else ""
        if "429" in stderr or "rate limit" in stderr:
            logging.warning(f"Rate limit exceeded for key ending in '...{api_key[-4:]}'.")
            raise RateLimitException("429 Rate Limit Exceeded")
        
        logging.error(f"Gemini command failed: {e.stderr}")
        return None, 0

    except FileNotFoundError as e:
        spinner.stop()
        logging.error(f"Gemini command failed: {e}")
        return None, 0
    except json.JSONDecodeError as e:
        spinner.stop()
        logging.error(f"Failed to decode Gemini CLI JSON output: {e}")
        return result.stdout.strip(), 0


def parse_command_from_response(response):
    """
    Parses a shell command from a fenced code block (```bash) in the response.
    """
    match = re.search(r"```bash\n(.*?)\n```", response, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None

def execute_shell_command(command, permissions_level, is_interactive, task_id, current_prompt, response):
    """
    Executes a shell command after validating it, logs the action, and streams the output.
    """
    logging.info(f"Attempting to execute shell command: {command} with '{permissions_level}' permissions.")
    command_base = command.split()[0]

    # --- Permission Check ---
    can_execute = False
    if permissions_level == 'superuser':
        if command_base in SUPERUSER_DENIED_COMMANDS:
            error_message = f"Execution denied: Command '{command_base}' is on the superuser denylist."
            logging.error(error_message)
            return error_message, False
        can_execute = True
    else: # 'weak' mode is the default
        if command_base in WEAK_ALLOWED_COMMANDS:
            can_execute = True
        elif is_interactive:
            logging.warning(f"Command '{command_base}' is not on the weak allowlist.")
            user_input = input(f"Allow execution of this command just once? (y/n): ")
            if user_input.lower() == 'y':
                can_execute = True
        
        if not can_execute:
            error_message = f"Execution denied: Command '{command_base}' is not on the allowlist and was not approved by the user."
            logging.error(error_message)
            return error_message, False

    # --- Database Logging (Pre-execution) ---
    conn = db_utils.get_db_connection()
    command_log_id = None
    if conn:
        try:
            with conn.cursor() as cur:
                agent_mode = "agentic" if is_interactive else "interactive" # is_interactive is True for both agentic and interactive modes
                command_log_id = db_utils.log_command(cur, task_id, current_prompt, response, command, permissions_level, can_execute, agent_mode)
                # Set status to 'running' immediately
                cur.execute("UPDATE command_log SET status = 'running', command_start_timestamp = NOW() WHERE id = %s;", (command_log_id,))
                conn.commit()
        except Exception as e:
            logging.error(f"Database error during pre-execution logging: {e}")
            if conn:
                conn.rollback()
    else:
        logging.error("Could not log command to database; connection failed.")


    # --- Execution & Streaming ---
    logging.info(f"Command '{command_base}' approved for execution. Streaming output...")
    try:
        process = subprocess.Popen(
            command, shell=True, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        
        full_stdout = ""
        full_stderr = ""

        print("--- Command Output (Streaming) ---")
        while True:
            output = process.stdout.readline()
            if output:
                print(output.strip())
                full_stdout += output
            
            error = process.stderr.readline()
            if error:
                print(error.strip(), file=sys.stderr)
                full_stderr += error

            if process.poll() is not None and not output and not error:
                break
        print("--- End of Command Output ---")
        
        success = process.returncode == 0
        # Log the output and final status
        if conn and command_log_id:
            with conn.cursor() as cur:
                db_utils.log_command_output(cur, command_log_id, full_stdout, full_stderr, process.returncode, None, success)
                # Update status to 'completed' or 'failed'
                final_status = 'completed' if success else 'failed'
                cur.execute("UPDATE command_log SET status = %s, command_end_timestamp = NOW() WHERE id = %s;", (final_status, command_log_id))
                conn.commit()
        
        return f"STDOUT:\n{full_stdout}\nSTDERR:\n{full_stderr}", success

    except Exception as e:
        error_output = f"Failed to execute command: {e}"
        logging.error(error_output)
        if conn and command_log_id:
            with conn.cursor() as cur:
                db_utils.log_command_output(cur, command_log_id, "", str(e), -1, None, False)
                # Update status to 'failed' on exception
                cur.execute("UPDATE command_log SET status = 'failed', command_end_timestamp = NOW() WHERE id = %s;", (command_log_id,))
                conn.commit()
        return error_output, False
    finally:
        if conn:
            conn.close()


def main():
    """Main function for the interactive and agentic Gemini agent."""
    parser = argparse.ArgumentParser(description="Gemini Distributed Agent")
    parser.add_argument('prompt', type=str, help="The initial prompt or instruction.")
    parser.add_argument('--interactive', action='store_true', help="Ask for confirmation before executing tasks.")
    parser.add_argument('--agentic', action='store_true', help="Execute tasks autonomously until completion.")
    parser.add_argument('--permissions', type=str, default='weak', choices=['weak', 'superuser'], help="Set the permission level for command execution.")
    parser.add_argument('--task-id', type=str, default=None, help="The specific task ID to resume or use for context.")
    
    args = parser.parse_args()

    if args.interactive and args.agentic:
        print("Error: Cannot use --interactive and --agentic flags simultaneously.")
        return

    current_prompt = args.prompt
    # Check if the prompt is a file path and read its content
    if os.path.isfile(current_prompt):
        try:
            with open(current_prompt, 'r') as f:
                current_prompt = f.read()
            logging.info(f"Loaded prompt from file: {args.prompt}")
        except Exception as e:
            logging.error(f"Failed to read prompt from file {args.prompt}: {e}")
            print(f"Error: Could not read file '{args.prompt}'. Please check the path and permissions.")
            return
            
    session_context = []

    db_utils.send_slack_notification(f"Agent starting up for prompt: {current_prompt}", level="info")
    logging.info(f"Agent starting up for prompt: {current_prompt}")
    
    conn = db_utils.get_db_connection()
    if not conn:
        db_utils.send_slack_notification("Agent failed to connect to the database.", level="error")
        return

    redis_conn = db_utils.get_redis_connection()

    # --- Retry Logic Variables ---
    max_retries = 5
    retry_delay = 5 # seconds
    # ---

    try:
        with conn.cursor() as cur:
            # Use the provided task_id or generate a default one
            task_id = args.task_id if args.task_id else db_utils.get_task_id()
            logging.info(f"Using task ID: {task_id}")
            
            # Get the task, which now just ensures the task entry exists.
            session_context_data = db_utils.get_or_create_task(cur, task_id)
            
            retry_count = 0
            while True: # Main agent loop
                key_info = db_utils.get_available_key(cur, redis_conn)
                if not key_info:
                    message = f"No available API keys. Sleeping for {KEY_EXHAUSTED_SLEEP_MINUTES} minutes."
                    db_utils.send_slack_notification(message, level="warning")
                    logging.warning(message)
                    time.sleep(KEY_EXHAUSTED_SLEEP_MINUTES * 60)
                    continue

                key_name, api_key = key_info
                logging.info(f"Selected API key: {key_name}")
                db_utils.throttle_if_needed(cur, key_name)

                # Separate base context from history
                base_context = session_context_data.get('base_context')
                
                # Load the history for the task using the new relational method
                session_context = db_utils.get_task_history(cur, task_id)

                try:
                    response, token_count = run_gemini_command(api_key, current_prompt, session_context, base_context)
                except RateLimitException:
                    logging.warning(f"Key '{key_name}' is rate-limited. Cycling to the next key.")
                    # Mark the key as temporarily disabled
                    cur.execute("UPDATE api_keys SET disabled_until = NOW() + INTERVAL '5 minutes' WHERE key_name = %s;", (key_name,))
                    conn.commit()
                    # Clear the Redis cache to force a refresh from the DB
                    if redis_conn:
                        redis_conn.delete(db_utils.REDIS_KEY_LIST)
                    continue # Move to the next iteration to get a new key
                
                if not response:
                    retry_count += 1
                    if retry_count > max_retries:
                        logging.error(f"No response from Gemini after {max_retries} retries. Stopping.")
                        db_utils.send_slack_notification(f"Agent stopping: No response from Gemini after {max_retries} retries for task {task_id}.", level="error")
                        break
                    
                    logging.warning(f"No response from Gemini. Retrying in {retry_delay} seconds... (Attempt {retry_count}/{max_retries})")
                    time.sleep(retry_delay)
                    retry_delay *= 2 # Exponential backoff
                    continue

                # Reset retry count on successful response
                retry_count = 0
                retry_delay = 5

                # Add the new interaction to the relational history
                db_utils.add_interaction_to_history(cur, task_id, current_prompt, response)

                print(f"\nResponse:\n{response}\n")

                db_utils.update_key_and_log_usage(cur, key_name, task_id, token_count, "gemma-agentic" if args.agentic else "gemma-interactive")
                db_utils.check_and_notify_quota_usage(cur, key_name) # Check quota after usage
                conn.commit()

                command_to_run = parse_command_from_response(response)

                if not command_to_run:
                    logging.info("No executable command found in the response. Stopping.")
                    break

                should_execute = False
                if args.agentic:
                    logging.info(f"--- Agentic Mode: Executing command automatically ---")
                    should_execute = True
                elif args.interactive:
                    user_input = input(f"Execute the following command? \n\n{command_to_run}\n\n(y/n): ")
                    if user_input.lower() == 'y':
                        should_execute = True

                if should_execute:
                    command_output, success = execute_shell_command(
                        command_to_run, 
                        args.permissions, 
                        args.interactive or args.agentic,
                        task_id,
                        current_prompt,
                        response
                    )
                    
                    if success:
                        current_prompt = f"The last command was successful. The output was:\n\n{command_output}\n\nBased on this and our history, what is the next command to continue the task? If the task is complete, respond with only the text 'TASK_COMPLETE'."
                    else:
                        current_prompt = f"The last command failed. The output was:\n\n{command_output}\n\nBased on this and our history, what is the next command to continue the task? If the task is complete, respond with only the text 'TASK_COMPLETE'."
                else:
                    logging.info("Execution cancelled by user or mode. Stopping.")
                    break
                
                if "TASK_COMPLETE" in response:
                    logging.info("Task marked as complete by the model. Stopping.")
                    break

    except Exception as e:
        error_message = f"An unexpected error occurred: {e}"
        db_utils.send_slack_notification(error_message, level="error")
        logging.error(error_message, exc_info=True)
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()
            logging.info("Database connection closed.")
    
    logging.info("Agent shutting down.")

if __name__ == "__main__":
    main()