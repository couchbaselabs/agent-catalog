#!/bin/bash

cd "$(dirname "${BASH_SOURCE[0]}")" || exit

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 [controlflow]"
    exit 1
fi

trap on_ctrl_c INT
function on_ctrl_c() {
    echo "Ctrl-C issued, killing spawned processes."
    kill "$(ps -ef | grep -E 'agent_server.py|prefect|rewards_server.py|uvicorn' | grep -v 'grep' | awk '{print $2}')"
}

if [ "$1" == "controlflow" ]; then
  echo "Spawning new Prefect server."
  prefect server start &
  echo "Starting agent server."
  fastapi run services/agent_server.py --port 10000 &

else
  echo "Invalid argument. Usage: $0 [controlflow]"
  exit 1
fi

echo "Starting (dummy) rewards server."

echo "Starting UI."
streamlit run app.py
