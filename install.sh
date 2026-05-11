#!/bin/bash
# Intelligence — one-time install script (no Docker required)
# After this finishes, use:  bash start.sh  /  bash stop.sh

set -e
cd "$(dirname "$0")"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
RESET='\033[0m'

ok()   { echo -e "${GREEN}✓${RESET} $1"; }
warn() { echo -e "${YELLOW}⚠${RESET}  $1"; }
fail() { echo -e "${RED}✗${RESET} $1"; echo ""; exit 1; }
step() { echo -e "\n${BOLD}$1${RESET}"; }
hr()   { echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"; }

echo ""
echo -e "${BOLD}Intelligence — Install${RESET}"
hr
echo ""

# ── Step 1: Python 3.11+ ──────────────────────────────────────────────────────
step "1 / 5  Python"

# Prefer python3.11+ explicitly if available, fall back to python3
if command -v python3.11 &>/dev/null; then
    PYTHON_BIN=python3.11
elif command -v python3.12 &>/dev/null; then
    PYTHON_BIN=python3.12
elif command -v python3.13 &>/dev/null; then
    PYTHON_BIN=python3.13
elif command -v python3 &>/dev/null; then
    PYTHON_BIN=python3
else
    fail "Python 3 not found.

  Install Python 3.11 or newer:
    macOS:   brew install python@3.11
    Linux:   sudo apt install python3.11 python3.11-venv  (Debian/Ubuntu)
             sudo dnf install python3.11                  (Fedora/RHEL)

  Then run this script again."
fi

PY_MAJOR=$("$PYTHON_BIN" -c 'import sys; print(sys.version_info.major)')
PY_MINOR=$("$PYTHON_BIN" -c 'import sys; print(sys.version_info.minor)')
PY_VER="$PY_MAJOR.$PY_MINOR"

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 11 ]; }; then
    fail "Python 3.11+ required — found $PY_VER.

  Install a newer version:
    macOS:   brew install python@3.11
    Linux:   sudo apt install python3.11 python3.11-venv

  Then run this script again."
fi

ok "Python $PY_VER ($PYTHON_BIN)"

# ── Step 2: Node.js 18+ ───────────────────────────────────────────────────────
step "2 / 5  Node.js (required for the web UI)"

if ! command -v node &>/dev/null || ! command -v npm &>/dev/null; then
    fail "Node.js not found. The web UI requires Node.js 18 or newer.

  Install options:
    macOS:   brew install node
    Linux:   curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
             sudo apt install -y nodejs

    Or download directly: https://nodejs.org  (choose the LTS version)

  Then run this script again."
fi

NODE_VER=$(node --version)
NODE_MAJOR=$(node --version | tr -d 'v' | cut -d. -f1)
if [ "$NODE_MAJOR" -lt 18 ]; then
    fail "Node.js 18+ required — found $NODE_VER.

  Upgrade:
    macOS:   brew upgrade node
    Linux:   curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
             sudo apt install -y nodejs

  Then run this script again."
fi

ok "Node.js $NODE_VER, npm $(npm --version)"

# ── Step 3: Python virtual environment ───────────────────────────────────────
step "3 / 5  Python environment"

if [ -d venv ]; then
    # Verify the existing venv is usable
    if venv/bin/python -c "import sys" &>/dev/null 2>&1; then
        ok "Virtual environment exists"
    else
        warn "Existing venv appears broken — recreating it..."
        rm -rf venv
        "$PYTHON_BIN" -m venv venv
        ok "Virtual environment recreated"
    fi
else
    echo "  Creating virtual environment..."
    "$PYTHON_BIN" -m venv venv
    ok "Virtual environment created"
fi

echo "  Installing Python dependencies (2–4 min first time — chromadb is large)..."
venv/bin/pip install -q --upgrade pip
venv/bin/pip install -q -r requirements.txt
ok "Python dependencies installed"

# ── Step 4: Gemini API key ────────────────────────────────────────────────────
step "4 / 5  Gemini API key"

if [ ! -f .env ]; then
    [ -f .env.example ] && cp .env.example .env || echo "GEMINI_API_KEY=your_gemini_api_key_here" > .env
fi

current_key=$(grep -E "^GEMINI_API_KEY=" .env 2>/dev/null | cut -d= -f2 | tr -d '"' | tr -d "'" | tr -d '[:space:]')

if [ -z "$current_key" ] || [ "$current_key" = "your_gemini_api_key_here" ]; then
    echo ""
    echo "  A free Gemini API key is required for AI article analysis."
    echo "  Get one in 30 seconds (no credit card) at:"
    echo ""
    echo "    https://aistudio.google.com/apikey"
    echo ""
    read -r -p "  Paste your Gemini API key: " user_key
    user_key=$(echo "$user_key" | tr -d '[:space:]')
    [ -z "$user_key" ] && fail "No key entered. Run install.sh again when you have the key."

    if grep -q "^GEMINI_API_KEY=" .env; then
        sed -i.bak "s|^GEMINI_API_KEY=.*|GEMINI_API_KEY=${user_key}|" .env && rm -f .env.bak
    else
        echo "GEMINI_API_KEY=${user_key}" >> .env
    fi
    ok "API key saved to .env"
else
    ok "API key already set (${current_key:0:8}…)"
fi

# ── Step 5: Frontend ──────────────────────────────────────────────────────────
step "5 / 5  Building web UI"

echo "  Installing npm dependencies..."
npm install --silent
echo "  Building frontend..."
npm run build --silent
ok "Web UI built — will be served at http://localhost:8001"

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
hr
echo -e "${GREEN}${BOLD}Install complete.${RESET}"
echo ""
echo "  Start:   bash start.sh"
echo "  Stop:    bash stop.sh"
echo "  Logs:    tail -f api.log scheduler.log"
echo ""
echo "  On first start the scheduler immediately runs a news fetch."
echo "  After that it runs automatically at 7am, noon, and 3pm."
echo ""
