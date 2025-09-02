import os
from utils import db_utils
import logging
from dotenv import load_dotenv

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def populate_keys_from_env():
    """
    Reads API keys from the file specified by the API_KEYS_FILE environment variable
    and populates them into the database.
    """
    # Load environment variables from the project's .env file
    # This ensures that API_KEYS_FILE and POSTGRES_ENV_FILE are available
    dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
    load_dotenv(dotenv_path=dotenv_path)
    
    keys_file = os.getenv("API_KEYS_FILE")
    if not keys_file:
        logging.error("API_KEYS_FILE not set in environment. Aborting.")
        return

    if not os.path.exists(keys_file):
        logging.error(f"Keys file not found at: {keys_file}. Aborting.")
        return

    logging.info(f"Reading keys from: {keys_file}")
    
    with open(keys_file, 'r') as f:
        # Using a dictionary to prevent duplicate key names
        keys = {}
        for line in f:
            if '=' in line:
                name, value = line.strip().split('=', 1)
                keys[name] = value

    if not keys:
        logging.warning("No keys found in the file.")
        return

    # Get a database connection using the centralized utility
    conn = db_utils.get_db_connection()
    if not conn:
        logging.error("Failed to connect to the database. Aborting.")
        return
    
    try:
        with conn.cursor() as cur:
            for name, value in keys.items():
                cur.execute("SELECT key_name FROM api_keys WHERE key_name = %s;", (name,))
                if cur.fetchone():
                    logging.info(f"Key '{name}' already exists. Skipping.")
                else:
                    cur.execute(
                        "INSERT INTO api_keys (key_name, key_value) VALUES (%s, %s);",
                        (name, value)
                    )
                    logging.info(f"Added new key: {name}")
            conn.commit()
            logging.info("Successfully populated/updated keys in the database.")
    except Exception as e:
        logging.error(f"An error occurred during database operation: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    populate_keys_from_env()