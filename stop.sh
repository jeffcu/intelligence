#!/bin/bash
cd "$(dirname "$0")"

for pidfile in frontend.pid api.pid scheduler.pid; do
    if [ -f "$pidfile" ]; then
        pid=$(cat "$pidfile")
        kill "$pid" 2>/dev/null && echo "Stopped $(basename $pidfile .pid) (PID $pid)" || true
        rm -f "$pidfile"
    fi
done

echo "Intelligence stopped."
