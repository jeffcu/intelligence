#!/bin/bash
# Intelligence — start API + scheduler
# Run install.sh first if you haven't already.

set -e
cd "$(dirname "$0")"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
RESET='\033[0m'

ok()   { echo -e "${GREEN}✓${RESET} $1"; }
warn() { echo -e "${YELLOW}⚠${RESET}  $1"; }
fail() { echo -e "${RED}✗${RESET} $1"; exit 1; }

# ── Pre-flight ────────────────────────────────────────────────────────────────
if [ ! -d venv ]; then
    fail "Virtual environment not found. Run:  bash install.sh"
fi

if [ ! -f .env ]; then
    fail ".env file missing. Run:  bash install.sh"
fi

PYTHON=venv/bin/python

# ── Kill any stale processes from a previous run ──────────────────────────────
for pidfile in scheduler.pid api.pid; do
    if [ -f "$pidfile" ]; then
        old_pid=$(cat "$pidfile")
        if kill -0 "$old_pid" 2>/dev/null; then
            kill "$old_pid" 2>/dev/null && echo "Stopped stale $(basename $pidfile .pid) (PID $old_pid)"
        fi
        rm -f "$pidfile"
    fi
done

# ── Start API ─────────────────────────────────────────────────────────────────
"$PYTHON" api.py >> api.log 2>&1 &
API_PID=$!
echo $API_PID > api.pid
ok "API started (PID $API_PID) — logging to api.log"

# ── Wait for API to be ready ──────────────────────────────────────────────────
echo -n "  Waiting for API"
max_wait=60
waited=0
while ! curl -sf http://localhost:8001/health &>/dev/null; do
    sleep 2
    waited=$((waited + 2))
    printf "."
    if [ $waited -ge $max_wait ]; then
        echo ""
        fail "API did not start within ${max_wait}s. Check the log:  tail -50 api.log"
    fi
done
echo " ready."

# ── Start scheduler ───────────────────────────────────────────────────────────
# Starts after the API is confirmed up so it doesn't compete with port binding.
"$PYTHON" news_scheduler.py >> scheduler.log 2>&1 &
SCHED_PID=$!
echo $SCHED_PID > scheduler.pid
ok "Scheduler started (PID $SCHED_PID) — logging to scheduler.log"

# ── Report ────────────────────────────────────────────────────────────────────
echo ""
health=$(curl -sf http://localhost:8001/health 2>/dev/null || echo '{}')
key_status=$(echo "$health" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('api_key','?'))" 2>/dev/null || echo "unknown")

if [[ "$key_status" == *"MISSING"* ]]; then
    warn "API is running but Gemini key is not set — edit .env and restart."
else
    ok "Gemini key configured"
fi

echo ""
echo "  Intelligence running at:  http://localhost:8001"
echo ""
echo "  Useful commands:"
echo "    tail -f api.log            — watch API output"
echo "    tail -f scheduler.log      — watch scheduler / ingest output"
echo "    bash stop.sh               — stop everything"
echo ""
