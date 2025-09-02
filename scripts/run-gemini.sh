#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
cd "$DIR"
source venv/bin/activate
exec python gemini_interactive_wrapper.py "$@"
