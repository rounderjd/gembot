import json
import os
import argparse
import random
import requests

def get_llm_config():
    """Loads the LLM configuration file."""
    config_path = os.path.join(os.path.dirname(__file__), 'llm_platform_config.json')
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found at {config_path}")
    with open(config_path, 'r') as f:
        return json.load(f)

def choose_gemini_key(keys):
    """Selects a random Gemini API key."""
    return random.choice(list(keys.values()))

def call_ollama(prompt, config):
    """Sends a request to the local Ollama server."""
    ollama_config = config.get('ollama', {})
    base_url = ollama_config.get('base_url', 'http://localhost:11434/api/generate') # Changed to the correct endpoint
    model = ollama_config.get('model', 'llama3')

    print(f"Sending prompt to Ollama at {base_url} using model '{model}'...")

    try:
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False  # We want the full response at once
        }
        response = requests.post(base_url, json=payload)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
        
        # The response from Ollama is a stream of JSON objects, even with stream:false. We'll parse the last one.
        full_response = response.text
        last_json_line = full_response.strip().split('\n')[-1]
        response_data = json.loads(last_json_line)

        return response_data.get('response', 'No response content from Ollama.')

    except requests.exceptions.RequestException as e:
        return f"Error connecting to Ollama: {e}\nIs the Ollama server running?"
    except json.JSONDecodeError as e:
        return f"Error decoding Ollama's response: {e}\nResponse text: {response.text}"


def route_prompt(prompt):
    """
    Analyzes the prompt to decide where to send it.
    Simple logic: if 'ollama' or 'local' is in the prompt, use Ollama.
    Otherwise, default to Gemini.
    """
    if "ollama" in prompt.lower() or "local" in prompt.lower():
        return "ollama"
    elif "code" in prompt.lower() or "python" in prompt.lower():
        return "openai"
    else:
        return "gemini"

def main():
    """Main function for the LLM router."""
    parser = argparse.ArgumentParser(description="Intelligent LLM Router")
    parser.add_argument('prompt', type=str, help="The prompt to send to the LLM.")
    args = parser.parse_args()

    try:
        config = get_llm_config()
    except FileNotFoundError as e:
        print(e)
        return

    llm_choice = route_prompt(args.prompt)
    print(f"Routing decision: '{llm_choice}'")

    if llm_choice == "gemini":
        api_key = choose_gemini_key(config['gemini'])
        print(f"Using Gemini with key ending in: ...{api_key[-4:]}")
        print("\n--- Gemini Response ---")
        print("TODO: Implement Gemini API call using the selected key.")
        # Example of how you might call it:
        # response = call_gemini(args.prompt, api_key)
        # print(response)

    elif llm_choice == "openai":
        api_key = config['openai']['api_key']
        if api_key == "YOUR_OPENAI_API_KEY":
            print("OpenAI API key not configured. Please edit llm_platform_config.json")
            return
        print(f"Using OpenAI with key ending in: ...{api_key[-4:]}")
        print("\n--- OpenAI Response ---")
        print("TODO: Implement OpenAI API call.")

    elif llm_choice == "ollama":
        print("\n--- Ollama Response ---")
        response = call_ollama(args.prompt, config)
        print(response)


if __name__ == "__main__":
    main()