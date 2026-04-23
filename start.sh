#!/bin/bash
cd "$(dirname "$0")"

if [ ! -d venv ]; then
    python3 -m venv venv
    venv/bin/pip install -r requirements.txt
fi

PYTHON=venv/bin/python

# Kill any stale scheduler
if [ -f scheduler.pid ]; then
    kill "$(cat scheduler.pid)" 2>/dev/null || true
fi

# Start scheduler in background
"$PYTHON" news_scheduler.py &
echo $! > scheduler.pid
echo "Scheduler started (PID $(cat scheduler.pid))"

# Start API (foreground — Ctrl+C stops both)
exec "$PYTHON" api.py
