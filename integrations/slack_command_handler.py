

import os
import hmac
import hashlib
import time
from flask import Flask, request, jsonify
import threading
import subprocess
import requests
import logging

# --- Configuration ---
from dotenv import load_dotenv

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(dotenv_path=os.path.join(ROOT, ".env"), override=True)

# Slack secrets from env
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")

# Where to run the contextual script (default to repo root)
GEMINI_SCRIPT_PATH = os.getenv("GEMINI_SCRIPT_PATH", os.path.join(ROOT, "run_gemini_contextual.py"))

# Log file under repo logs/
LOG_FILE = os.getenv("SLACK_HANDLER_LOG_FILE", os.path.join(ROOT, "logs", "slack_handler.log"))
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

app = Flask(__name__)

def verify_slack_request(request):
    """Verifies the signature of an incoming Slack request."""
    timestamp = request.headers.get('X-Slack-Request-Timestamp')
    signature = request.headers.get('X-Slack-Signature')
    
    if not timestamp or not signature:
        return False

    # Prevent replay attacks
    if abs(time.time() - int(timestamp)) > 60 * 5:
        return False

    if not SLACK_SIGNING_SECRET:
        logging.error("SLACK_SIGNING_SECRET is not set. Cannot verify request.")
        return False

    req_body = request.get_data(as_text=True)
    base_string = f"v0:{timestamp}:{req_body}".encode('utf-8')
    secret = SLACK_SIGNING_SECRET.encode('utf-8')
    
    my_signature = 'v0=' + hmac.new(secret, base_string, hashlib.sha256).hexdigest()
    
    return hmac.compare_digest(my_signature, signature)

def run_gemini_and_respond(prompt, response_url, task_id):
    """Runs the Gemini script in a background thread and sends the result to Slack."""
    logging.info(f"Running Gemini for task '{task_id}' with prompt: {prompt}")
    
    try:
        # Execute the script
        result = subprocess.run(
            ["python3", GEMINI_SCRIPT_PATH, prompt, task_id],
            capture_output=True,
            text=True,
            timeout=300 # 5-minute timeout
        )
        
        if result.returncode == 0:
            response_text = f"✅ *Task '{task_id}' successful:*\n\n{result.stdout}"
        else:
            response_text = f"❌ *Task '{task_id}' failed:*\n\n*Stderr:*\n{result.stderr}\n*Stdout:*\n{result.stdout}"

    except subprocess.TimeoutExpired:
        response_text = f"⌛️ *Task '{task_id}' timed out after 5 minutes.*"
    except Exception as e:
        response_text = f"🚨 *An unexpected error occurred while running the agent for task '{task_id}':*\n\n{str(e)}"

    # Send the result back to Slack
    requests.post(response_url, json={"text": response_text})
    logging.info(f"Sent response to Slack for task '{task_id}'.")


@app.route('/slack/gemini', methods=['POST'])
def slack_gemini_command():
    """Endpoint to receive slash commands from Slack."""
    if not verify_slack_request(request):
        logging.warning("Invalid Slack signature received.")
        return jsonify({"error": "Invalid signature"}), 403

    # Extract data from the form payload
    data = request.form
    prompt = data.get('text')
    response_url = data.get('response_url')
    
    # Use the channel ID and user ID to create a unique, persistent task ID
    channel_id = data.get('channel_id')
    user_id = data.get('user_id')
    task_id = f"slack-{channel_id}-{user_id}"

    if not prompt:
        return jsonify({"text": "Please provide a prompt. Usage: /gemini <your prompt>"})

    # Acknowledge the command immediately
    ack_text = f"Got it. Running your prompt against task context `{task_id}`. Please wait..."
    
    # Start the background job
    thread = threading.Thread(
        target=run_gemini_and_respond,
        args=(prompt, response_url, task_id)
    )
    thread.start()
    
    return jsonify({"text": ack_text})

if __name__ == '__main__':
    logging.info("Starting Slack command handler server.")
    # Listen on all interfaces on port 5001
    app.run(host='0.0.0.0', port=5001)

