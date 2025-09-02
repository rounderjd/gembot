# Gemini System: `gembot.sh`

This document provides a comprehensive overview of the `gembot.sh` Gemini agent system.

---

## System Overview

The `gembot.sh` system is a sophisticated, database-backed platform for running the Gemini CLI in a persistent, multi-agent environment. It features a PostgreSQL database for logging and API key management.

### System Architecture and Features:

- **Entry Point**: `/srv/gemini/gembot.sh`
- **Launcher Script**: `/srv/gemini/launcher/launch_gemini_task.sh`
- **API Key Selector**: `/srv/gemini/launcher/scripts/select_key.py`
- **Configuration**: `/srv/gemini/launcher/config/.env`

#### Key Features:

*   **Database-Driven API Key Management**:
    *   Uses a **PostgreSQL** database as the central component for API key management.
    *   The `select_key.py` script intelligently selects an available key based on its quota status (`daily_request_count < 60`), disabled status (`disabled_until`), and last use time (`last_used`).

*   **Execution Modes**:
    *   **`interactive` mode**: The default mode, which launches the Gemini CLI for interactive use.
    *   **`debug` mode**: A mode for debugging the launcher script.
    *   **`headless` mode**: A mode for running the Gemini CLI in a non-interactive way.

*   **Local npm Dependency Management**:
    *   The `@google/gemini-cli` npm package is installed locally in `/srv/gemini/node_modules`, ensuring that the application is self-contained and doesn't rely on a globally installed package.
