#!/usr/bin/env python3
import os
import sys

try:
    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
except ImportError:
    print("Error: The 'psycopg2-binary' library is required. Please install it by running:")
    print("pip install psycopg2-binary")
    sys.exit(1)

# --- Configuration ---
# Load database connection details from environment variables
# These are expected to be set in the .env file and loaded by the launcher
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_USER = os.getenv("DB_USER", "rootuser")
DB_PASSWORD = os.getenv("DB_PASSWORD", "gvh!qkm0yfd6CFY4kuv")
DB_ADMIN_DB = os.getenv("DB_ADMIN_DB", "postgres") # A default db to connect to for admin tasks
DB_NAME = os.getenv("DB_GEMINI_AGENT", "gemini_agent") # The new database we will create

# Path to the schema file, relative to this script's location
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEMA_PATH = os.path.join(SCRIPT_DIR, '..', 'config', 'schema.sql')

def create_database():
    """
    Connects to the PostgreSQL server and creates the new database if it doesn't exist.
    """
    conn = None
    try:
        # Connect to the default 'postgres' database to perform admin tasks
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            dbname=DB_ADMIN_DB
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()

        # Check if the database already exists
        cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DB_NAME,))
        if cursor.fetchone():
            print(f"Database '{DB_NAME}' already exists. Skipping creation.")
        else:
            print(f"Creating database '{DB_NAME}'...")
            cursor.execute(f"CREATE DATABASE {DB_NAME}")
            print("Database created successfully.")

        cursor.close()
    except psycopg2.OperationalError as e:
        print(f"Error: Could not connect to PostgreSQL at {DB_HOST}:{DB_PORT}.")
        print("Please ensure the database is running and the connection details are correct.")
        print(f"Details: {e}")
        sys.exit(1)
    finally:
        if conn:
            conn.close()

def apply_schema():
    """
    Connects to the newly created database and applies the schema from the .sql file.
    """
    conn = None
    try:
        # Connect to the new database
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            dbname=DB_NAME
        )
        cursor = conn.cursor()

        print(f"Applying schema from '{SCHEMA_PATH}'...")
        with open(SCHEMA_PATH, 'r') as f:
            sql_script = f.read()
            cursor.execute(sql_script)

        conn.commit()
        print("Schema applied successfully. All tables are created.")
        cursor.close()
    except FileNotFoundError:
        print(f"Error: Schema file not found at '{SCHEMA_PATH}'.")
        sys.exit(1)
    except Exception as e:
        print(f"An error occurred while applying the schema: {e}")
        sys.exit(1)
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    print("--- Gemini Agent Database Setup ---")
    create_database()
    apply_schema()
    print("---------------------------------")
    print("Setup complete.")
