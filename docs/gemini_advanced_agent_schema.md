# 🤖 Advanced Agent Orchestration and Knowledge Persistence for Gemini Distributed Agents

This document outlines additional enhancements beyond the base PostgreSQL schema to support:

- Agent self-orchestration across nodes
- Memory of prior commands, permissions, network state
- Personalization of agent behavior
- Optimization of API key usage
- Modular deployment via `.env` or JSON-based configuration

---

## I. 🧠 Extended Knowledge and Personalization Schema

### `user_profile`
Personal user preferences, permission defaults, and interaction styles.

```sql
CREATE TABLE user_profile (
  id SERIAL PRIMARY KEY,
  username TEXT UNIQUE,
  default_permissions TEXT,
  throttle_tolerance INT,
  max_token_per_request INT,
  timezone TEXT,
  preferred_format TEXT
);
```

### `home_network`
Stores metadata about machines and services in your network.

```sql
CREATE TABLE home_network (
  id SERIAL PRIMARY KEY,
  host_name TEXT,
  ip_address TEXT,
  service TEXT,
  notes TEXT,
  tags TEXT[],
  last_seen TIMESTAMP
);
```

### `permissions_profile`
Remembers user-approved commands and permission tolerances.

```sql
CREATE TABLE permissions_profile (
  id SERIAL PRIMARY KEY,
  user_id TEXT,
  command TEXT,
  last_used TIMESTAMP,
  allow_by_default BOOLEAN,
  notes TEXT
);
```

### `custom_knowledge`
Long-term memory for facts, patterns, personal configurations.

```sql
CREATE TABLE custom_knowledge (
  id SERIAL PRIMARY KEY,
  task_id TEXT REFERENCES tasks(id),
  label TEXT,
  value TEXT,
  source TEXT,
  tags TEXT[],
  visibility TEXT DEFAULT 'private',
  inserted_at TIMESTAMP DEFAULT NOW()
);
```

---

## II. 🔁 Enhanced API Key Optimization

### Added Columns to `api_keys`

```sql
ALTER TABLE api_keys
ADD COLUMN priority INT DEFAULT 0,
ADD COLUMN assigned_user TEXT,
ADD COLUMN rotating BOOLEAN DEFAULT TRUE,
ADD COLUMN source TEXT;
```

Use `priority`, `assigned_user`, and `rotating` to coordinate API key usage across many agents.

---

## III. 🧮 Token Forecasting + Analytics

### `token_prediction_log`
Used to track estimated vs actual token usage for optimizing prompts and batching.

```sql
CREATE TABLE token_prediction_log (
  id SERIAL PRIMARY KEY,
  task_id TEXT,
  api_key TEXT,
  predicted_tokens INT,
  actual_tokens INT,
  delta INT,
  request_timestamp TIMESTAMP DEFAULT NOW()
);
```

---

## IV. 🧬 Embedding / Vector Memory (Optional)

If using pgvector:

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE vector_knowledge (
  id SERIAL PRIMARY KEY,
  embedding VECTOR(768),
  source TEXT,
  metadata JSONB
);
```

---

## V. 🤖 Multi-Agent Coordination and Deployment

### `subtasks`
Allows a parent agent to delegate work to other agents or machines.

```sql
CREATE TABLE subtasks (
  id SERIAL PRIMARY KEY,
  parent_task_id TEXT REFERENCES tasks(id),
  child_task_id TEXT,
  description TEXT,
  status TEXT DEFAULT 'pending',
  assigned_host TEXT,
  agent_mode TEXT,
  created_at TIMESTAMP DEFAULT NOW(),
  started_at TIMESTAMP,
  completed_at TIMESTAMP
);
```

### `agents`
Registry of online/offline agents and their capabilities.

```sql
CREATE TABLE agents (
  id TEXT PRIMARY KEY,
  hostname TEXT,
  ip_address TEXT,
  last_heartbeat TIMESTAMP,
  capabilities TEXT[],
  current_task_id TEXT,
  status TEXT
);
```

### `task_queue` (if Redis is not used)

```sql
CREATE TABLE task_queue (
  id SERIAL PRIMARY KEY,
  target_host TEXT,
  payload JSONB,
  created_at TIMESTAMP DEFAULT NOW(),
  claimed BOOLEAN DEFAULT FALSE,
  claimed_by TEXT,
  claimed_at TIMESTAMP
);
```

---

## VI. 🔧 Configuration via `.env` or `agent_config.json`

All tunable variables can be externalized to environment or JSON:

```json
{
  "permissions": {
    "weak": {
      "allowlist": ["ls", "cat", "curl"]
    },
    "superuser": {
      "denylist": ["rm", "shutdown", "reboot"]
    }
  },
  "api_policy": {
    "max_tokens_per_key": 240000,
    "max_requests_per_day": 60,
    "rpm_soft_limit": 2
  },
  "agent_defaults": {
    "mode": "agentic",
    "permissions": "weak"
  }
}
```

`.env` example:

```dotenv
POSTGRES_DB=gemini_distributed_agent
POSTGRES_USER=agent
POSTGRES_PASSWORD=supersecret
GEMINI_CLI_COMMAND=/usr/local/bin/gemini
GEMINI_API_KEY_FILE=/path/to/api_keys.env
```

---

## ✅ Summary

These schema and coordination enhancements enable:

- Memory-aware, personalized LLM agents
- Delegation of subtasks across machines
- Optimized API key usage via DB coordination
- Replayable and queryable execution trace
- Searchable, structured personal knowledge base