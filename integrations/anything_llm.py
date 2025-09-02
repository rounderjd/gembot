
import os
import requests
from dotenv import load_dotenv

# Load environment variables from .env file
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path=dotenv_path)

ANYTHING_LLM_API_KEY = os.getenv("ANYTHING_LLM_API_KEY")
ANYTHING_LLM_API_URL = os.getenv("ANYTHING_LLM_API_URL")

def send_to_anything_llm(prompt, context):
    """
    Sends a prompt and context to the AnythingLLM API.
    """
    if not ANYTHING_LLM_API_KEY or not ANYTHING_LLM_API_URL:
        return "AnythingLLM API key or URL not configured."

    headers = {
        "Authorization": f"Bearer {ANYTHING_LLM_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "prompt": prompt,
        "context": context
    }

    try:
        response = requests.post(ANYTHING_LLM_API_URL, headers=headers, json=data)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return f"Error connecting to AnythingLLM: {e}"

