# Distributed Gemini CLI Agent System (Design + Ops Manual)

**Last updated:** 2025-07-26

---

## 🎯 Goal

Build a distributed system for interacting with Gemini CLI that:

- Rotates through many Gemini API keys across machines.
- Stores persistent context and task history in a central PostgreSQL database.
- Avoids free-tier quota limits (Requests Per Minute, Tokens Per Minute, Requests Per Day).
- Can resume tasks after shutdown using prior context.
- Tracks all token usage and request events for auditing or debugging.
- Operates ethically within Google Cloud’s terms of service.

---

## 📊 Quota Constraints (Free Tier, Gemini Pro 2.5)

| Quota Type       | Value          | Notes                             |
|------------------|----------------|------------------------------------|
| Requests/Minute  | ~2–5           | **Most fragile**; causes 429 easily |
| Tokens/Minute    | 250,000        | Rarely hit unless sending long content |
| Requests/Day     | ~60–120        | Per API key/project; resets midnight PT |

---

## 🛠️ PostgreSQL Schema

```sql
CREATE TABLE api_keys (
  id SERIAL PRIMARY KEY,
  key_name TEXT UNIQUE NOT NULL,
  key_value TEXT NOT NULL,
  last_used TIMESTAMP,
  quota_exhausted BOOLEAN DEFAULT FALSE,
  daily_request_count INT DEFAULT 0,
  daily_token_total INT DEFAULT 0,
  disabled_until TIMESTAMP
);

CREATE TABLE usage_log (
  id SERIAL PRIMARY KEY,
  key_name TEXT,
  task_id TEXT,
  request_timestamp TIMESTAMP DEFAULT NOW(),
  token_count INT,
  request_type TEXT
);

CREATE TABLE tasks (
  id TEXT PRIMARY KEY,
  context JSONB,
  last_updated TIMESTAMP DEFAULT NOW(),
  status TEXT
);
```

---

## 🌀 API Key Rotation Script (`cycle_key.sh`)

```bash
KEY=$(psql your_db -t -A -c "
  SELECT key_value FROM api_keys
  WHERE NOT quota_exhausted
    AND (disabled_until IS NULL OR disabled_until < NOW())
    AND daily_request_count < 60
    AND daily_token_total < 240000
  ORDER BY last_used NULLS FIRST
  LIMIT 1;
")

if [ -z "$KEY" ]; then
  echo 'All keys exhausted. Sleeping 5m...'
  sleep 300
  exec "$0"
fi

export GEMINI_API_KEY="$KEY"
psql your_db -c "UPDATE api_keys SET last_used = NOW() WHERE key_value = '$KEY';"
```

---

## 🧠 Agent Behavior on Startup

1. Derive `TASK_ID` using hostname and date.
2. Query context from `tasks` using `TASK_ID`.
3. If found, resume session; else insert a new task entry.
4. Run Gemini CLI using the restored context.
5. Log tokens used, request type, and time.
6. Update key stats and throttle if needed.

---

## 🧯 Throttling RPM

To avoid 429s:

```bash
MIN_INTERVAL=30
LAST_USED=$(psql ... "SELECT EXTRACT(EPOCH FROM (NOW() - last_used)) FROM api_keys WHERE key_value = '$GEMINI_API_KEY';")

if (( $(echo "$LAST_USED < $MIN_INTERVAL" | bc -l) )); then
  SLEEP_TIME=$(echo "$MIN_INTERVAL - $LAST_USED" | bc -l)
  echo "Throttling... sleeping $SLEEP_TIME"
  sleep "$SLEEP_TIME"
fi
```

---

## 🔁 Daily Quota Reset

Set a daily cron:

```bash
0 8 * * * psql your_db -c "
  UPDATE api_keys SET
    daily_token_total = 0,
    daily_request_count = 0,
    quota_exhausted = FALSE,
    disabled_until = NULL;"
```

---

## 🧩 Ethical Scaling Strategy

- Use 1–3 real Google accounts.
- Each creates ~20 projects with unique Gemini API keys.
- Rotate projects, **not accounts**.
- Avoid automated Gmail generation (violates ToS).
- Billing can be enabled with no cost if you stay under quota.

---

## 📁 Extras

- Store API keys in `.env` or DB, not in source code.
- Optionally integrate Slack or MQTT for real-time ops.
- Use systemd timers or Docker to relaunch agents on reboot.
