#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
PYTHON_EXEC="$DIR/venv/bin/python"
GEMINI_WRAPPER="$DIR/gemini_interactive_wrapper.py"
if [ ! -x "$PYTHON_EXEC" ]; then echo "Missing venv Python: $PYTHON_EXEC" >&2; exit 1; fi
exec "$PYTHON_EXEC" "$GEMINI_WRAPPER" "$@"
