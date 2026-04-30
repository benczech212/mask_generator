#!/bin/bash
cd "$(dirname "$0")/.."
if [ -f run.pid ]; then
    PID=$(cat run.pid)
    kill $PID
    rm run.pid
    echo "App stopped (PID $PID)"
else
    echo "run.pid not found. Is the app running?"
    pkill -f "python app.py"
    echo "Attempted to pkill app.py"
fi
