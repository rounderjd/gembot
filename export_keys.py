
import json
import os
from utils import db_utils

def export_keys():
    """
    Fetches API keys from the database and exports them to a JSON file.
    """
    print("Connecting to the database...")
    conn = db_utils.get_db_connection()
    if not conn:
        print("Failed to connect to the database. Please check your configuration.")
        return

    print("Fetching Gemini API keys...")
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT key_name, key_value FROM api_keys;")
            gemini_keys = {row[0]: row[1] for row in cur.fetchall()}
    except Exception as e:
        print(f"Error fetching keys from the database: {e}")
        conn.close()
        return
    finally:
        conn.close()

    print(f"Found {len(gemini_keys)} Gemini API keys.")

    config = {
        "gemini": gemini_keys,
        "openai": {
            "api_key": "YOUR_OPENAI_API_KEY"
        },
        "merlin": {
            "api_key": "YOUR_MERLIN_API_KEY"
        }
    }

    config_path = os.path.join(os.path.dirname(__file__), 'llm_platform_config.json')
    print(f"Writing configuration to {config_path}...")
    try:
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=4)
        print("Successfully exported API keys.")
    except Exception as e:
        print(f"Error writing configuration file: {e}")

if __name__ == "__main__":
    export_keys()
