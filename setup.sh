#!/bin/bash
# Intelligence — one-command setup script
# Works on macOS and Linux. Run once after cloning the repo.
# Usage: bash setup.sh

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
RESET='\033[0m'

ok()   { echo -e "${GREEN}✓${RESET} $1"; }
warn() { echo -e "${YELLOW}⚠${RESET}  $1"; }
fail() { echo -e "${RED}✗${RESET} $1"; }
step() { echo -e "\n${BOLD}$1${RESET}"; }

echo ""
echo -e "${BOLD}Intelligence — Setup${RESET}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ── Step 1: Docker ────────────────────────────────────────────────────────────
step "1 / 5  Checking Docker"

if ! command -v docker &>/dev/null; then
    fail "Docker is not installed."
    echo ""
    echo "  Download Docker Desktop from: https://www.docker.com/products/docker-desktop"
    echo "  Install it, open it, and wait for the whale icon in the menu bar."
    echo "  Then run this script again."
    exit 1
fi

if ! docker info &>/dev/null 2>&1; then
    fail "Docker is installed but not running."
    echo ""
    echo "  Open Docker Desktop from your Applications folder."
    echo "  Wait for the whale icon in the menu bar to stop animating."
    echo "  Then run this script again."
    exit 1
fi

ok "Docker is running  ($(docker --version | awk '{print $3}' | tr -d ','))"

# ── Step 2: Port check ────────────────────────────────────────────────────────
step "2 / 5  Checking port 8001"

if lsof -i :8001 &>/dev/null 2>&1; then
    warn "Port 8001 is already in use."
    echo ""
    echo "  Something else is using port 8001. To see what:"
    echo "    lsof -i :8001"
    echo ""
    echo "  Option A: Stop whatever is using port 8001, then re-run setup.sh"
    echo "  Option B: Edit docker-compose.yml, change  '8001:8001'  to  '8002:8001'"
    echo "            then access Intelligence at http://localhost:8002"
    echo ""
    read -r -p "  Continue anyway? (y/N): " cont
    [[ "$cont" =~ ^[Yy]$ ]] || exit 1
else
    ok "Port 8001 is free"
fi

# ── Step 3: .env file ─────────────────────────────────────────────────────────
step "3 / 5  Setting up API key"

if [ ! -f ".env" ]; then
    cp .env.example .env
    warn "Created .env from template — you need to add your Gemini API key."
fi

# Check if the key is still the placeholder
current_key=$(grep -E "^GEMINI_API_KEY=" .env | cut -d= -f2 | tr -d '"' | tr -d "'")
if [ -z "$current_key" ] || [ "$current_key" = "your_gemini_api_key_here" ]; then
    echo ""
    echo "  You need a free Gemini API key."
    echo "  Get one here (takes 30 seconds, no credit card required):"
    echo ""
    echo "    https://aistudio.google.com/apikey"
    echo ""
    read -r -p "  Paste your Gemini API key here: " user_key
    user_key=$(echo "$user_key" | tr -d '[:space:]')

    if [ -z "$user_key" ]; then
        fail "No key entered. Edit .env manually and set GEMINI_API_KEY=your_key"
        exit 1
    fi

    # Write key into .env
    if grep -q "^GEMINI_API_KEY=" .env; then
        sed -i.bak "s|^GEMINI_API_KEY=.*|GEMINI_API_KEY=${user_key}|" .env && rm -f .env.bak
    else
        echo "GEMINI_API_KEY=${user_key}" >> .env
    fi
    ok "API key saved to .env"
else
    ok "API key already configured (${current_key:0:8}…)"
fi

# ── Step 4: Build and start ───────────────────────────────────────────────────
step "4 / 5  Building and starting Intelligence"
echo "  This takes 2–4 minutes the first time (downloading and building)."
echo "  Subsequent starts take about 5 seconds."
echo ""

docker compose up -d --build

# Wait for the API to come up
echo ""
echo "  Waiting for API to start…"
max_wait=60
waited=0
while ! curl -sf http://localhost:8001/health &>/dev/null; do
    sleep 2
    waited=$((waited + 2))
    if [ $waited -ge $max_wait ]; then
        fail "API did not start within ${max_wait}s. Check logs with: docker logs intelligence"
        exit 1
    fi
    printf "."
done
echo ""

# Check health response
health=$(curl -sf http://localhost:8001/health 2>/dev/null || echo '{}')
key_status=$(echo "$health" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('api_key','?'))" 2>/dev/null || echo "unknown")

if [[ "$key_status" == *"MISSING"* ]]; then
    warn "API is running but Gemini key is not recognized."
    echo "  Check your .env file and restart: docker compose restart"
else
    ok "API is running and healthy"
fi

# ── Step 5: Next steps ────────────────────────────────────────────────────────
step "5 / 5  Done!"

echo ""
echo "  Intelligence is running at:  http://localhost:8001"
echo ""
echo "  ┌──────────────────────────────────────────────────────┐"
echo "  │  NEXT STEPS (do these in order)                      │"
echo "  │                                                       │"
echo "  │  1. Open http://localhost:8001 in your browser        │"
echo "  │  2. Click 'Edit' in the Tracking panel               │"
echo "  │  3. Add a ticker (e.g. AAPL) or topic (e.g. Gold)    │"
echo "  │  4. Run your first news fetch:                        │"
echo "  │     docker exec intelligence python ingestor.py       │"
echo "  │  5. Articles appear in 1–2 minutes                    │"
echo "  │                                                       │"
echo "  │  The scheduler runs automatically after that.         │"
echo "  └──────────────────────────────────────────────────────┘"
echo ""
echo "  Useful commands:"
echo "    docker logs intelligence          — see what's happening"
echo "    docker compose down               — stop Intelligence"
echo "    docker compose up -d              — start it again"
echo "    docker exec intelligence python ingestor.py   — fetch news now"
echo "    docker exec intelligence python summarizer.py — refresh briefings"
echo ""
