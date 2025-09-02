--
-- PostgreSQL schema for Gemini Distributed Agent System
-- Adapted from gemini_advanced_agent_schema.md
--

-- For optional vector support
CREATE EXTENSION IF NOT EXISTS vector;

-- Stores personal user preferences and interaction styles.
CREATE TABLE IF NOT EXISTS user_profile (
  id SERIAL PRIMARY KEY,
  username TEXT UNIQUE,
  default_permissions TEXT,
  throttle_tolerance INT,
  max_token_per_request INT,
  timezone TEXT,
  preferred_format TEXT
);

-- Stores metadata about machines and services in the local network.
CREATE TABLE IF NOT EXISTS home_network (
  id SERIAL PRIMARY KEY,
  host_name TEXT,
  ip_address TEXT,
  service TEXT,
  notes TEXT,
  tags TEXT[],
  last_seen TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Remembers user-approved commands and permission tolerances.
CREATE TABLE IF NOT EXISTS permissions_profile (
  id SERIAL PRIMARY KEY,
  user_id TEXT,
  command TEXT,
  last_used TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  allow_by_default BOOLEAN,
  notes TEXT
);

-- Main table for tasks, serves as a parent for logs and subtasks.
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    description TEXT,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Long-term memory for facts, patterns, and personal configurations.
CREATE TABLE IF NOT EXISTS custom_knowledge (
  id SERIAL PRIMARY KEY,
  task_id TEXT REFERENCES tasks(id),
  label TEXT,
  value TEXT,
  source TEXT,
  tags TEXT[],
  visibility TEXT DEFAULT 'private',
  inserted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Manages API keys for various services.
CREATE TABLE IF NOT EXISTS api_keys (
    id SERIAL PRIMARY KEY,
    service_name TEXT NOT NULL,
    api_key TEXT NOT NULL,
    last_used TIMESTAMP WITH TIME ZONE,
    use_count INT DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    priority INT DEFAULT 0,
    assigned_user TEXT,
    rotating BOOLEAN DEFAULT TRUE,
    source TEXT,
    UNIQUE(service_name, api_key)
);

-- Tracks estimated vs actual token usage for optimizing prompts.
CREATE TABLE IF NOT EXISTS token_prediction_log (
  id SERIAL PRIMARY KEY,
  task_id TEXT REFERENCES tasks(id),
  api_key_id INT REFERENCES api_keys(id),
  predicted_tokens INT,
  actual_tokens INT,
  delta INT,
  request_timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Stores vector embeddings for semantic knowledge search.
CREATE TABLE IF NOT EXISTS vector_knowledge (
  id SERIAL PRIMARY KEY,
  embedding VECTOR(768), -- Assuming a 768-dimension embedding
  source TEXT,
  metadata JSONB,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Allows a parent agent to delegate work to other agents.
CREATE TABLE IF NOT EXISTS subtasks (
  id SERIAL PRIMARY KEY,
  parent_task_id TEXT REFERENCES tasks(id),
  child_task_id TEXT,
  description TEXT,
  status TEXT DEFAULT 'pending',
  assigned_host TEXT,
  agent_mode TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  started_at TIMESTAMP WITH TIME ZONE,
  completed_at TIMESTAMP WITH TIME ZONE
);

-- Registry of online/offline agents and their capabilities.
CREATE TABLE IF NOT EXISTS agents (
  id TEXT PRIMARY KEY,
  hostname TEXT,
  ip_address TEXT,
  last_heartbeat TIMESTAMP WITH TIME ZONE,
  capabilities TEXT[],
  current_task_id TEXT,
  status TEXT -- e.g., 'idle', 'busy', 'offline'
);

-- Logs prompts and responses for context and history.
CREATE TABLE IF NOT EXISTS context_log (
    id SERIAL PRIMARY KEY,
    task_id TEXT REFERENCES tasks(id),
    prompt TEXT,
    response TEXT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Logs shell commands executed by the agent.
CREATE TABLE IF NOT EXISTS command_log (
    id SERIAL PRIMARY KEY,
    task_id TEXT REFERENCES tasks(id),
    command TEXT,
    outcome_stdout TEXT,
    outcome_stderr TEXT,
    exit_code INT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- A simple task queue if Redis is not used.
-- Note: Redis is generally preferred for this purpose.
CREATE TABLE IF NOT EXISTS task_queue (
  id SERIAL PRIMARY KEY,
  target_host TEXT,
  payload JSONB,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  claimed BOOLEAN DEFAULT FALSE,
  claimed_by TEXT,
  claimed_at TIMESTAMP WITH TIME ZONE
);

-- Add some initial data if needed, e.g., a default user
INSERT INTO user_profile (username, preferred_format)
VALUES ('default_user', 'markdown')
ON CONFLICT (username) DO NOTHING;
