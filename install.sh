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

# Ask user yes/no; return 0 for yes, 1 for no
ask_install() {
    local prompt="$1"
    printf "  %s [Y/n]: " "$prompt"
    read -r answer
    case "$answer" in
        [nN]*) return 1 ;;
        *)     return 0 ;;
    esac
}

# Detect OS for platform-specific guidance
IS_MAC=false
if [[ "$(uname)" == "Darwin" ]]; then IS_MAC=true; fi

echo ""
echo -e "${BOLD}Intelligence — Install${RESET}"
hr
echo ""

# ── Pre-flight: Homebrew (macOS only) ─────────────────────────────────────────
if $IS_MAC && ! command -v brew &>/dev/null; then
    warn "Homebrew not found — it is needed to install Python, Node.js, and Git."
    echo ""
    echo "  Homebrew is a free Mac package manager that installs developer tools"
    echo "  with a single command. See https://brew.sh for details."
    echo ""
    if ask_install "Install Homebrew now?"; then
        echo "  Installing Homebrew (you may be asked for your Mac password)..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        # Add brew to PATH for Apple Silicon if needed
        if [ -x /opt/homebrew/bin/brew ]; then
            eval "$(/opt/homebrew/bin/brew shellenv)"
        fi
        ok "Homebrew installed"
    else
        fail "Homebrew is required on macOS. Run this script again when Homebrew is installed."
    fi
fi

# ── Step 1: Python 3.11+ ──────────────────────────────────────────────────────
step "1 / 5  Python"

# Prefer python3.11+ explicitly if available, fall back to python3
find_python() {
    for cmd in python3.13 python3.12 python3.11 python3; do
        if command -v "$cmd" &>/dev/null; then
            echo "$cmd"; return
        fi
    done
}

PYTHON_BIN=$(find_python)

# If nothing found, or version is too old, offer to install
needs_python=false
if [ -z "$PYTHON_BIN" ]; then
    needs_python=true
else
    PY_MAJOR=$("$PYTHON_BIN" -c 'import sys; print(sys.version_info.major)')
    PY_MINOR=$("$PYTHON_BIN" -c 'import sys; print(sys.version_info.minor)')
    if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 11 ]; }; then
        warn "Found Python $PY_MAJOR.$PY_MINOR — version 3.11 or newer is required."
        needs_python=true
    fi
fi

if $needs_python; then
    if $IS_MAC && command -v brew &>/dev/null; then
        if ask_install "Python 3.11+ not found. Install it now via Homebrew?"; then
            echo "  Installing Python 3.11 (this may take a minute)..."
            brew install python@3.11
            PYTHON_BIN=python3.11
        else
            fail "Python 3.11+ is required. Run this script again after installing Python."
        fi
    else
        fail "Python 3.11+ not found.
  Install it:
    macOS:  brew install python@3.11
    Linux:  sudo apt install python3.11 python3.11-venv
  Then run this script again."
    fi
fi

PY_VER=$("$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
ok "Python $PY_VER ($PYTHON_BIN)"

# ── Step 2: Node.js 18+ ───────────────────────────────────────────────────────
step "2 / 5  Node.js (required for the web UI)"

needs_node=false
if ! command -v node &>/dev/null || ! command -v npm &>/dev/null; then
    needs_node=true
else
    NODE_MAJOR=$(node --version | tr -d 'v' | cut -d. -f1)
    if [ "$NODE_MAJOR" -lt 18 ]; then
        warn "Found Node.js $(node --version) — version 18 or newer is required."
        needs_node=true
    fi
fi

if $needs_node; then
    if $IS_MAC && command -v brew &>/dev/null; then
        if ask_install "Node.js 18+ not found. Install it now via Homebrew?"; then
            echo "  Installing Node.js (this may take a minute)..."
            brew install node
        else
            fail "Node.js 18+ is required (it builds the web interface). Run this script again after installing Node.js."
        fi
    else
        fail "Node.js 18+ not found.
  Install it:
    macOS:  brew install node
    Linux:  curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - && sudo apt install -y nodejs
  Then run this script again."
    fi
fi

NODE_VER=$(node --version)
ok "Node.js $NODE_VER, npm $(npm --version)"

# ── Git check (informational — git clone already happened if we're running) ───
if ! command -v git &>/dev/null; then
    warn "git not found — you will need it for future updates."
    if $IS_MAC && command -v brew &>/dev/null; then
        if ask_install "Install Git now via Homebrew?"; then
            brew install git
            ok "Git installed"
        fi
    fi
fi

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
