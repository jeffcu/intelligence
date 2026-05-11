#!/bin/bash
# Intelligence — stop API + scheduler

cd "$(dirname "$0")"

stopped=0
for pidfile in api.pid scheduler.pid; do
    if [ -f "$pidfile" ]; then
        pid=$(cat "$pidfile")
        name=$(basename "$pidfile" .pid)
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null
            echo "Stopped $name (PID $pid)"
            stopped=$((stopped + 1))
        else
            echo "$name (PID $pid) was not running"
        fi
        rm -f "$pidfile"
    fi
done

if [ $stopped -eq 0 ]; then
    echo "Nothing was running."
fi
