#!/bin/bash
# Intelligence — start API + scheduler (daily use)
# First-time setup: run install.sh

cd "$(dirname "$0")"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
RESET='\033[0m'

ok()   { echo -e "${GREEN}✓${RESET} $1"; }
warn() { echo -e "${YELLOW}⚠${RESET}  $1"; }
fail() { echo -e "${RED}✗${RESET} $1"; echo ""; exit 1; }

echo ""
echo -e "${BOLD}Intelligence — Starting${RESET}"
echo ""

# ── Pre-flight checks ─────────────────────────────────────────────────────────

# Venv: create and install if missing, verify if present
if [ ! -d venv ]; then
    warn "No virtual environment found — creating one now..."
    if ! command -v python3 &>/dev/null; then
        fail "Python 3 not found. Run install.sh first."
    fi
    python3 -m venv venv
    venv/bin/pip install -q --upgrade pip
    venv/bin/pip install -q -r requirements.txt
    ok "Virtual environment created and dependencies installed"
elif ! venv/bin/python -c "import fastapi" &>/dev/null 2>&1; then
    warn "Virtual environment exists but dependencies are missing — installing now..."
    venv/bin/pip install -q --upgrade pip
    venv/bin/pip install -q -r requirements.txt
    ok "Dependencies installed"
fi

PYTHON=venv/bin/python

# .env
if [ ! -f .env ]; then
    fail ".env file missing. Run install.sh to set up your Gemini API key."
fi

# Built frontend
if [ ! -d dist ]; then
    warn "Web UI not built — building now (requires Node.js)..."
    if ! command -v npm &>/dev/null; then
        fail "npm not found. Install Node.js 18+ then run install.sh."
    fi
    npm install --silent
    npm run build --silent
    ok "Web UI built"
fi

# ── Kill any stale processes ───────────────────────────────────────────────────
for pidfile in api.pid scheduler.pid; do
    if [ -f "$pidfile" ]; then
        old_pid=$(cat "$pidfile")
        if kill -0 "$old_pid" 2>/dev/null; then
            kill "$old_pid" 2>/dev/null
            echo "  Stopped stale $(basename $pidfile .pid) (PID $old_pid)"
        fi
        rm -f "$pidfile"
    fi
done

# Also evict any process holding port 8001 that wasn't in a pidfile
port_pid=$(lsof -ti:8001 2>/dev/null)
if [ -n "$port_pid" ]; then
    kill "$port_pid" 2>/dev/null && echo "  Evicted orphan on port 8001 (PID $port_pid)"
    sleep 1
fi

# ── Start API ──────────────────────────────────────────────────────────────────
"$PYTHON" api.py >> api.log 2>&1 &
echo $! > api.pid
ok "API started (PID $(cat api.pid))"

# ── Wait for API to respond ────────────────────────────────────────────────────
echo -n "  Waiting for API"
max_wait=60
waited=0
while ! curl -sf http://localhost:8001/health &>/dev/null; do
    sleep 2
    waited=$((waited + 2))
    printf "."
    if [ $waited -ge $max_wait ]; then
        echo ""
        fail "API did not respond within ${max_wait}s.
  Check the log for errors:  tail -30 api.log"
    fi
done
echo " ready."

# ── Start scheduler ────────────────────────────────────────────────────────────
# Starts after the API is confirmed up so chromadb init doesn't race port bind.
"$PYTHON" news_scheduler.py >> scheduler.log 2>&1 &
echo $! > scheduler.pid
ok "Scheduler started (PID $(cat scheduler.pid))"

# ── Status ────────────────────────────────────────────────────────────────────
health=$(curl -sf http://localhost:8001/health 2>/dev/null || echo '{}')
key_ok=$(echo "$health" | python3 -c "import sys,json; d=json.load(sys.stdin); print('yes' if 'MISSING' not in d.get('api_key','MISSING') else 'no')" 2>/dev/null || echo "no")

if [ "$key_ok" != "yes" ]; then
    warn "Gemini key not recognised — edit .env and run:  bash stop.sh && bash start.sh"
fi

echo ""
echo -e "  ${BOLD}http://localhost:8001${RESET}  ← open this in your browser"
echo ""
echo "  Logs:  tail -f api.log scheduler.log"
echo "  Stop:  bash stop.sh"
echo ""
