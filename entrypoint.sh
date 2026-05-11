#!/bin/sh
set -e

DATA_DIR="${DATA_DIR:-/app/data}"
mkdir -p "$DATA_DIR"

# Point DB and chroma to the persistent volume
export DB_PATH="$DATA_DIR/intelligence.db"
export CHROMA_PATH="$DATA_DIR/chroma_db"

echo "=== Intelligence container starting ==="
echo "  Data dir : $DATA_DIR"
echo "  DB path  : $DB_PATH"
echo "  Chroma   : $CHROMA_PATH"
echo "  Python   : $(python --version 2>&1)"

# Start the API first so the health endpoint responds quickly.
# The scheduler is launched after a short pause so it doesn't
# compete with the API's port bind during the chromadb cold-start.
python api.py &
API_PID=$!
echo "  API PID  : $API_PID (starting in background)"

# Give the API a few seconds to bind the port before the scheduler
# starts its heavy chromadb / ONNX initialization.
sleep 5

echo "  Starting news scheduler..."
python news_scheduler.py &
SCHED_PID=$!
echo "  Sched PID: $SCHED_PID"

echo "=== Startup complete. Tailing API process. ==="

# Block on the API process so Docker has a meaningful PID 1.
# If the API crashes the container exits and Docker restarts it.
wait $API_PID
