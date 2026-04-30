#!/bin/bash
cd "$(dirname "$0")/.."
source venv/bin/activate
nohup python app.py > app.log 2>&1 &
echo $! > run.pid
echo "App started on port 5000 (PID $(cat run.pid))"
