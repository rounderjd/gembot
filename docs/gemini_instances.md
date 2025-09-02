# Gemini Instances

This document outlines the different instances of the Gemini agent and their configurations.

## `gembot.sh`

*   **Location**: `/srv/gemini/gembot.sh`
*   **Purpose**: This is the primary entry point for the Gemini CLI on this system. It's a wrapper script that handles environment setup, API key management, and launching the Gemini CLI.
*   **Key Management**: It uses a sophisticated, database-backed API key management system. The script `select_key.py` selects an available key from a PostgreSQL database, based on its quota status, disabled status, and last use time.
*   **Execution Modes**: It supports `interactive`, `debug`, and `headless` modes.
*   **Dependencies**:
    *   Python 3
    *   pip
    *   npm
    *   PostgreSQL
*   **Configuration**: The database connection and other settings are configured in `/srv/gemini/launcher/config/.env`.