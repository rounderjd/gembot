# 🧠 Using Gemini CLI as the Frontend Shell with Enhanced Agent Infrastructure

This document outlines how to preserve the familiar **Gemini CLI user interface** while fully leveraging your enhanced distributed agent system. Gemini CLI becomes the UI **frontend**, while your launcher handles:

- API key rotation
- Context persistence
- Subtask logging
- Command history
- Permission profiling

---

## 🎯 Goals

- Keep Gemini CLI as the interactive shell for human agents.
- Use a custom launcher to enforce agent coordination logic.
- Allow agents to log context and results across machines.
- Support CLI-only or automated agentic operation via flags.

---

## 🧰 Requirements

- Your enhanced schema and `common-scripts/` helpers
- The official `@google/gemini-cli` installed (`npm install -g`)
- A `.env` or `agent_config.json` with:
  - API quota settings
  - Task metadata
  - Host/agent mappings

---

## 🚀 Launcher Script Design: `launch_gemini_task.sh`

This wrapper performs the following:

1. Accepts a `--task_id` and optional mode
2. Selects the optimal API key
3. Populates prior context
4. Starts Gemini CLI using the selected key
5. Logs all user input/output
6. Records token usage and permission grants

```bash
#!/bin/bash
set -e

TASK_ID="$1"
MODE="${2:-interactive}"

# Load env
source /srv/countrycat/gemini/.env

# Get next API key
GEMINI_API_KEY=$(python3 /srv/countrycat/common-scripts/select_key.py --task_id "$TASK_ID")
export GEMINI_API_KEY

# Load context
python3 /opt/gemini-distributed-agent/utils/populate_context.py --task_id "$TASK_ID"

# Launch Gemini CLI shell
/usr/local/bin/gemini

# Log session
python3 /srv/countrycat/common-scripts/log_session.py --task_id "$TASK_ID"
```

---

## 💡 Command Usage

```bash
./launch_gemini_task.sh task-20250727
```

OR launch in agent mode:

```bash
./launch_gemini_task.sh task-20250727 agentic
```

---

## 🧱 Optional JSON Config

You can specify API policy, permissions, and routing in a JSON file:

```json
{
  "api_policy": {
    "max_tokens_per_key": 240000,
    "rpm_soft_limit": 2
  },
  "agent_defaults": {
    "mode": "interactive",
    "permissions": "weak"
  }
}
```

This allows dynamic parameter loading and remote tuning.

---

## 🗃️ What Is Logged to the Database

| Table                 | Description                              |
|----------------------|------------------------------------------|
| `tasks`              | Task ID, description, timestamps         |
| `context_log`        | Prompt/response pairs                    |
| `command_log`        | Shell commands issued and outcomes       |
| `token_prediction_log` | Estimated vs actual token usage       |
| `permissions_profile`| Approved or denied shell actions         |

---

## 🔌 Optional Enhancements

- Pipe Gemini output through `tee` to log to file
- Wrap CLI in `tmux` for web UI (e.g. ttyd or wetty)
- Add Slack command trigger to launch with pre-filled task ID

---

## ✅ Benefits

- Retains human-facing shell of Gemini CLI
- Unlocks full multi-agent, DB-backed coordination
- Enables personalized memory, context, and safe automation
- Supports CLI, Slack, or future GUI without rewriting core logic