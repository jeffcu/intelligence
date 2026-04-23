#!/bin/sh
set -e

DATA_DIR="${DATA_DIR:-/app/data}"
mkdir -p "$DATA_DIR"

# Point DB and chroma to the persistent volume
export DB_PATH="$DATA_DIR/intelligence.db"
export CHROMA_PATH="$DATA_DIR/chroma_db"

echo "Intelligence starting — data at $DATA_DIR"

# Start scheduler in background
python news_scheduler.py &
SCHED_PID=$!
echo "Scheduler PID: $SCHED_PID"

# Start API in foreground (serves both API + built frontend)
exec python api.py
