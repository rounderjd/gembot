
import os
import psycopg2
from dotenv import load_dotenv

# Load database credentials from .postgres.env
dotenv_path = os.path.join(os.path.dirname(__file__), '.postgres.env')
load_dotenv(dotenv_path)

DB_NAME = os.getenv("POSTGRES_DB")
DB_USER = os.getenv("POSTGRES_USER")
DB_PASS = os.getenv("POSTGRES_PASSWORD")
DB_HOST = os.getenv("POSTGRES_HOST")
DB_PORT = os.getenv("POSTGRES_PORT")

def view_logs():
    """Connects to the database and prints the last 20 log entries."""
    conn = None
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            host=DB_HOST,
            port=DB_PORT
        )
        cur = conn.cursor()
        cur.execute("SELECT * FROM usage_log ORDER BY timestamp DESC LIMIT 20;")
        rows = cur.fetchall()
        
        if not rows:
            print("No log entries found.")
            return

        # Get column names from the cursor description
        colnames = [desc[0] for desc in cur.description]
        
        # Print header
        header = " | ".join(f"{name:<25}" for name in colnames)
        print(header)
        print("-" * len(header))

        # Print rows
        for row in rows:
            # Format each value, converting None to 'NULL' and ensuring alignment
            formatted_row = " | ".join(f"{str(value):<25}" for value in row)
            print(formatted_row)

    except psycopg2.Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    view_logs()
