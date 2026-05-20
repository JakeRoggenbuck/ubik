#!/usr/bin/env bash
# Wrapper for ubik that restarts the bot when it exits with code 42
# (used by the >update command after a git pull).
set -u

cd "$(dirname "$0")"

while true; do
    python main.py
    code=$?
    if [ "$code" -ne 42 ]; then
        exit "$code"
    fi
    echo "ubik exited with restart code; relaunching..."
done
