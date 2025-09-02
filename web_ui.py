import os
import subprocess
from flask import Flask, render_template, Response, request
import logging
from queue import Queue
from threading import Thread

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='/srv/gemini_workspace/web_ui.log',
    filemode='a'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# --- Paths ---
CODE_DIR = "/srv/gemini"
LAUNCHER = os.path.join(CODE_DIR, "launcher/launch_gemini_task.sh")

# --- Process Management ---
# WARNING: This is a simple solution for a single-user, single-process server.
# It will not scale to multiple users. A more robust solution would use
# a proper session management and process manager.
process = None
process_queue = Queue()

def process_manager(proc):
    """Read from the process's stdout and push to a queue."""
    for line in iter(proc.stdout.readline, ''):
        process_queue.put(line)
    proc.stdout.close()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/run')
def run():
    global process
    mode = request.args.get('mode')
    if not mode:
        return Response("Missing 'mode' parameter", status=400)

    def generate():
        global process
        try:
            # Terminate any existing process
            if process and process.poll() is None:
                process.terminate()
                process.wait()

            # Generate a unique TASK_ID
            env = os.environ.copy()
            env['TZ'] = 'America/Chicago'
            task_id_process = subprocess.run(
                ["date", "+%F-%H%M"],
                capture_output=True, text=True, check=True, env=env
            )
            task_id = task_id_process.stdout.strip()

            command = [LAUNCHER, task_id, mode]
            logger.info(f"Executing command: {' '.join(command)}")

            process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            # Start a thread to read from the process's stdout
            thread = Thread(target=process_manager, args=(process,))
            thread.daemon = True
            thread.start()

            while process.poll() is None or not process_queue.empty():
                try:
                    line = process_queue.get(timeout=0.1)
                    yield f"data: {line.strip()}\n\n"
                except Exception:
                    # Timeout just means no new output
                    pass

            logger.info(f"Command finished with exit code {process.returncode}")

        except subprocess.CalledProcessError as e:
            logger.error(f"Error executing command: {e}")
            yield f"data: Error: {e}\n\n"
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")
            yield f"data: An unexpected error occurred: {e}\n\n"

    return Response(generate(), mimetype='text/event-stream')

@app.route('/send', methods=['POST'])
def send():
    global process
    if not process or process.poll() is not None:
        return Response("No active process", status=400)

    message = request.json.get('message')
    if not message:
        return Response("Missing 'message' parameter", status=400)

    try:
        process.stdin.write(message + '\n')
        process.stdin.flush()
        return Response("Message sent", status=200)
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        return Response(f"Error: {e}", status=500)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
