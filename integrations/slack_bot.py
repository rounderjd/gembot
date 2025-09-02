import os
from dotenv import load_dotenv

# Resolve repo root from this file (…/integrations/ -> repo root)
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(dotenv_path=os.path.join(ROOT, ".env"), override=True)

import subprocess
import threading
from datetime import datetime
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

# --- Configuration ---
# Load environment variables from a .env file
load_dotenv(dotenv_path=os.path.join(ROOT, '.env'), override=True)
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN")
LOGS_DIR = os.path.join(os.path.dirname(__file__), 'gemma_logs')
BASE_URL = "http://localhost:5002"  # Adjust if your web UI is hosted elsewhere

# --- Slack App Initialization ---
app = App()

def execute_gemma_command(command, channel_id):
    """
    Executes the gemma command, logs the output, and sends a notification to Slack.
    """
    try:
        # Execute the command
        # We're assuming 'gemma' is in the system's PATH
        full_command = f"gemma {command}"
        result = subprocess.run(
            full_command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=600  # 10-minute timeout
        )

        # Prepare log content
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"gemma_log_{timestamp}.html"
        log_filepath = os.path.join(LOGS_DIR, log_filename)
        log_url = f"{BASE_URL}/gemma_logs/{log_filename}"

        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>Gemma Command Log</title>
            <style>
                body {{ font-family: monospace; background-color: #f4f4f9; color: #333; }}
                pre {{ white-space: pre-wrap; word-wrap: break-word; background-color: #fff; padding: 1em; border-radius: 5px; }}
            </style>
        </head>
        <body>
            <h1>Command:</h1>
            <pre>{full_command}</pre>
            <h1>Exit Code:</h1>
            <pre>{result.returncode}</pre>
            <h1>Stdout:</h1>
            <pre>{result.stdout or "No output."}</pre>
            <h1>Stderr:</h1>
            <pre>{result.stderr or "No errors."}</pre>
        </body>
        </html>
        """

        # Write the log file
        with open(log_filepath, "w") as f:
            f.write(html_content)

        # Send a summary notification to Slack
        summary = (
            f"Command `{command}` finished with exit code {result.returncode}."
            if result.returncode == 0
            else f"Command `{command}` failed with exit code {result.returncode}."
        )
        app.client.chat_postMessage(
            channel=channel_id,
            text=f"Gemma command execution finished.\n>{summary}\n<a href='{log_url}'>View full log</a>"
        )

    except subprocess.TimeoutExpired:
        app.client.chat_postMessage(
            channel=channel_id,
            text=f"The command `{command}` timed out after 10 minutes."
        )
    except Exception as e:
        app.client.chat_postMessage(
            channel=channel_id,
            text=f"An error occurred while executing the command `{command}`: {e}"
        )

@app.event("app_mention")
def handle_app_mention_events(body, say):
    """
    Handles mentions of the bot and executes the command.
    """
    text = body["event"]["text"]
    # Remove the mention from the text to get the command
    command = text.split(">", 1)[-1].strip()

    if not command:
        say("Please provide a command to execute.")
        return

    # Acknowledge the command and start execution in a separate thread
    say(f"Received your command: `{command}`. I'm on it!")
    
    thread = threading.Thread(
        target=execute_gemma_command,
        args=(command, body["event"]["channel"])
    )
    thread.start()

# --- Main Execution ---
if __name__ == "__main__":
    if not SLACK_BOT_TOKEN or not SLACK_APP_TOKEN:
        print("Error: SLACK_BOT_TOKEN and SLACK_APP_TOKEN must be set in the environment.")
    else:
        print("Starting Slack bot...")
        handler = SocketModeHandler(app, SLACK_APP_TOKEN)
        handler.start()

