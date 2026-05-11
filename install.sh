#!/bin/bash
# Intelligence — no-Docker install script
# Run once after cloning. Then use start.sh / stop.sh daily.
# Works on macOS and Linux with Python 3.11+.

set -e
cd "$(dirname "$0")"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
RESET='\033[0m'

ok()   { echo -e "${GREEN}✓${RESET} $1"; }
warn() { echo -e "${YELLOW}⚠${RESET}  $1"; }
fail() { echo -e "${RED}✗${RESET} $1"; exit 1; }
step() { echo -e "\n${BOLD}$1${RESET}"; }

echo ""
echo -e "${BOLD}Intelligence — Install (no Docker)${RESET}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ── Step 1: Python version ────────────────────────────────────────────────────
step "1 / 4  Checking Python"

if ! command -v python3 &>/dev/null; then
    fail "python3 not found. Install Python 3.11+ from https://python.org and try again."
fi

PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=$(python3 -c 'import sys; print(sys.version_info.major)')
PY_MINOR=$(python3 -c 'import sys; print(sys.version_info.minor)')

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 11 ]; }; then
    fail "Python 3.11+ required. Found $PY_VER. Download from https://python.org"
fi

ok "Python $PY_VER"

# ── Step 2: Virtual environment ───────────────────────────────────────────────
step "2 / 4  Setting up Python environment"

if [ ! -d venv ]; then
    echo "  Creating virtual environment..."
    python3 -m venv venv
    ok "Virtual environment created"
else
    ok "Virtual environment already exists"
fi

echo "  Installing / updating dependencies (this takes 2-4 min the first time)..."
venv/bin/pip install -q --upgrade pip
venv/bin/pip install -q -r requirements.txt
ok "Dependencies installed"

# ── Step 3: API key ───────────────────────────────────────────────────────────
step "3 / 4  Gemini API key"

if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env
    else
        echo "GEMINI_API_KEY=your_gemini_api_key_here" > .env
    fi
fi

current_key=$(grep -E "^GEMINI_API_KEY=" .env 2>/dev/null | cut -d= -f2 | tr -d '"' | tr -d "'")
if [ -z "$current_key" ] || [ "$current_key" = "your_gemini_api_key_here" ]; then
    echo ""
    echo "  You need a free Gemini API key (no credit card required):"
    echo "  https://aistudio.google.com/apikey"
    echo ""
    read -r -p "  Paste your key here: " user_key
    user_key=$(echo "$user_key" | tr -d '[:space:]')
    [ -z "$user_key" ] && fail "No key entered. Edit .env and set GEMINI_API_KEY=your_key, then run install.sh again."

    if grep -q "^GEMINI_API_KEY=" .env; then
        # macOS sed needs an extension argument; Linux does not — handle both
        sed -i.bak "s|^GEMINI_API_KEY=.*|GEMINI_API_KEY=${user_key}|" .env && rm -f .env.bak
    else
        echo "GEMINI_API_KEY=${user_key}" >> .env
    fi
    ok "API key saved to .env"
else
    ok "API key already set (${current_key:0:8}…)"
fi

# ── Step 4: Frontend (optional) ───────────────────────────────────────────────
step "4 / 4  Frontend"

if command -v node &>/dev/null && command -v npm &>/dev/null; then
    NODE_VER=$(node --version)
    echo "  Node $NODE_VER found — building frontend..."
    npm install -q
    npm run build -q
    ok "Frontend built — the API will serve it at http://localhost:8001"
else
    warn "Node.js not found — skipping frontend build."
    echo "  The API and scheduler will work fine without it."
    echo "  To add the web UI later: install Node.js 18+, then run:"
    echo "    npm install && npm run build"
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "${GREEN}Install complete.${RESET}"
echo ""
echo "  Start Intelligence:    bash start.sh"
echo "  Stop it:               bash stop.sh"
echo "  Watch the logs:        tail -f api.log scheduler.log"
echo ""
echo "  On first start the scheduler runs an immediate news fetch."
echo "  After that it runs at 7am, noon, and 3pm automatically."
echo ""
