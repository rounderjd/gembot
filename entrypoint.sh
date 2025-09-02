#!/bin/bash
set -e

# Start the Web UI in the background
python3 /app/web_ui.py &

# Start the main gembot menu
/usr/bin/env bash /app/gembot.sh
