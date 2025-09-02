# 🧠 Enhanced Database Schema for Gemini Distributed Agent

This document outlines a proposed expansion of the existing PostgreSQL schema to turn the database into a full knowledge and coordination layer for distributed Gemini CLI agents.

---

## ✅ Existing Tables

### `api_keys`
Tracks usage limits and throttling per API key.

### `tasks`
Stores task context, history, and status.

### `usage_log`
Logs request type, token usage, and key metadata.

---

## 🆕 Proposed Tables

### 1. `command_log`
Records each prompt, response, and proposed or executed command.

```sql
CREATE TABLE command_log (
  id SERIAL PRIMARY KEY,
  task_id TEXT REFERENCES tasks(id),
  executed_at TIMESTAMP DEFAULT NOW(),
  prompt TEXT,
  response TEXT,
  command TEXT,
  permissions TEXT,
  user_confirmation BOOLEAN,
  agent_mode TEXT -- 'interactive', 'agentic', etc.
);
```

---

### 2. `command_output`
Captures stdout/stderr and metadata for shell commands run by the agent.

```sql
CREATE TABLE command_output (
  id SERIAL PRIMARY KEY,
  command_log_id INT REFERENCES command_log(id),
  stdout TEXT,
  stderr TEXT,
  return_code INT,
  file_written TEXT,
  success BOOLEAN
);
```

---

### 3. `project_files`
Stores scanned file content for context population and reference.

```sql
CREATE TABLE project_files (
  id SERIAL PRIMARY KEY,
  task_id TEXT REFERENCES tasks(id),
  path TEXT,
  content TEXT,
  last_updated TIMESTAMP DEFAULT NOW()
);
```

---

### 4. `knowledge`
Structured summaries or extracted facts stored by the agent.

```sql
CREATE TABLE knowledge (
  id SERIAL PRIMARY KEY,
  task_id TEXT REFERENCES tasks(id),
  fact_label TEXT,
  fact_value TEXT,
  extracted_from TEXT, -- file, command, prompt, etc.
  confidence_score NUMERIC,
  inserted_at TIMESTAMP DEFAULT NOW()
);
```

---

## 🔁 Refactor Plan

| Existing Code                      | Update                                     |
|-----------------------------------|--------------------------------------------|
| `context['history'][]`            | Also insert into `command_log`             |
| `run_gemini_command(...)`         | Log `prompt`, `response`, and tokens       |
| `execute_shell_command(...)`      | Insert into `command_output`               |
| `populate_context.py`             | Insert into `project_files`                |
| `db_utils.py`                     | Add helpers for above table access         |

---

## 📈 Benefits

- 🔍 Full audit trail of every agent action
- 🔁 Resumable and traceable decision chains
- 📊 Searchable project memory across all agents
- 🧠 Long-term memory + inter-agent coordination