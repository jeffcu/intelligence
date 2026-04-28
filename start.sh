#!/bin/bash
set -e
cd "$(dirname "$0")"

if [ ! -d venv ]; then
    echo "Creating Python venv..."
    python3 -m venv venv
    venv/bin/pip install -q -r requirements.txt
fi

PYTHON=venv/bin/python

# Kill any stale processes from a previous run
for pidfile in scheduler.pid api.pid frontend.pid; do
    if [ -f "$pidfile" ]; then
        kill "$(cat "$pidfile")" 2>/dev/null || true
        rm -f "$pidfile"
    fi
done

# Start news scheduler in background
"$PYTHON" news_scheduler.py >> scheduler.log 2>&1 &
echo $! > scheduler.pid
echo "Scheduler started (PID $(cat scheduler.pid))"

# Start API in background
"$PYTHON" api.py >> api.log 2>&1 &
echo $! > api.pid
echo "API started (PID $(cat api.pid))"

# Wait for API health
echo -n "Waiting for Intelligence API"
for i in $(seq 1 30); do
    if curl -s http://localhost:8001/health > /dev/null 2>&1; then
        echo " ready."
        break
    fi
    echo -n "."
    sleep 1
done

# Install node deps if needed
if [ ! -d node_modules ]; then
    echo "Installing npm dependencies..."
    npm install -q
fi

# Start Vite dev server in background
npm run dev >> frontend.log 2>&1 &
echo $! > frontend.pid
echo "Frontend started (PID $(cat frontend.pid))"

LAN_IP="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo 'unknown')"
echo ""
echo "Intelligence running at:"
echo "  Local:   http://localhost:5174"
echo "  Network: http://${LAN_IP}:5174"
