import os
import json
import argparse
import logging
from utils import db_utils

# --- Configuration ---
# Files with these extensions will be read.
ALLOWED_EXTENSIONS = ['.md', '.txt', '.py', '.sh', '.json', '.yml', '.yaml', '.conf', '.cfg', '.ini', '.toml']
# Directories with these names will be ignored.
IGNORED_DIRECTORIES = ['.git', '__pycache__', 'node_modules', 'venv']

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def scan_directory_for_context(root_path):
    """
    Recursively scans a directory and reads the content of allowed file types.
    Returns a dictionary where keys are file paths and values are their content.
    """
    context_data = {}
    logging.info(f"Starting scan of directory: {root_path}")

    for dirpath, dirnames, filenames in os.walk(root_path):
        # Remove ignored directories from the list to prevent os.walk from traversing them
        dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRECTORIES]

        for filename in filenames:
            if any(filename.endswith(ext) for ext in ALLOWED_EXTENSIONS):
                file_path = os.path.join(dirpath, filename)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    # Use a relative path for the key to keep it clean
                    relative_path = os.path.relpath(file_path, root_path)
                    context_data[relative_path] = content
                    logging.info(f"Read and added context from: {relative_path}")
                except Exception as e:
                    logging.warning(f"Could not read file {file_path}: {e}")
    
    logging.info(f"Scan complete. Found {len(context_data)} files.")
    return context_data

def main():
    parser = argparse.ArgumentParser(description="Populate the agent's database with context from a directory.")
    parser.add_argument('directory', type=str, help="The absolute path to the directory to scan.")
    parser.add_argument('--task-id', type=str, required=True, help="The specific task ID to save this context under (e.g., 'countrycat-context').")
    
    args = parser.parse_args()

    if not os.path.isdir(args.directory):
        logging.error(f"Error: The specified directory does not exist: {args.directory}")
        return

    # 1. Scan the directory to get the context data
    project_context = scan_directory_for_context(args.directory)
    
    if not project_context:
        logging.warning("No files found to populate. Exiting.")
        return

    # 2. Connect to the database
    conn = db_utils.get_db_connection()
    if not conn:
        logging.error("Failed to connect to the database. Aborting.")
        return

    # 3. Save the context to the database
    try:
        with conn.cursor() as cur:
            # Check if the task exists to provide a clean starting context
            cur.execute("SELECT id FROM tasks WHERE id = %s;", (args.task_id,))
            task_exists = cur.fetchone()

            # Structure the new context for the database
            # We place the scanned files under a 'base_context' key
            new_context = {
                'base_context': project_context,
                'history': [] # Start with a clean history
            }

            if task_exists:
                logging.info(f"Task '{args.task_id}' already exists. Overwriting its context.")
                db_utils.update_task_context(cur, args.task_id, new_context)
            else:
                logging.info(f"Creating new task '{args.task_id}' with the scanned context.")
                cur.execute(
                    "INSERT INTO tasks (id, context, status) VALUES (%s, %s, %s);",
                    (args.task_id, json.dumps(new_context), 'active')
                )
            
            conn.commit()
            logging.info(f"Successfully populated database for task '{args.task_id}'.")

    except Exception as e:
        logging.error(f"An error occurred during database operation: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    main()
