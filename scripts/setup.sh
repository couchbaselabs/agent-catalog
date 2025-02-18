#!/bin/bash

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 {user|dev}"
  exit 1

elif [ "$1" != "user" ] && [ "$1" != "dev" ]; then
  echo "Invalid argument: $1"
  echo "Usage: $0 {user|dev}"
  exit 1
fi

LINE_LENGTH=$(tput cols)
printf '%*s\n' "$LINE_LENGTH" '' | tr ' ' '='
echo "Running ./scripts/setup.sh"
printf '%*s\n' "$LINE_LENGTH" '' | tr ' ' '='

# Get the directory of this script (only used for dev-mode).
SCRIPT_DIRECTORY=$(dirname -- "$(readlink -f -- "${BASH_SOURCE[0]}")")
echo "Using script directory: $SCRIPT_DIRECTORY"

# Install our dependencies with Poetry.
if [ "$1" == "user" ]; then
  poetry install
else
  poetry install --with docs
  mkdir -p "$SCRIPT_DIRECTORY/../libs/agentc_testing/agentc_testing/resources/models"
  poetry run python "$SCRIPT_DIRECTORY/../libs/agentc_testing/scripts/download_model.py"
fi

# Verify that Agent Catalog is correctly installed.
if poetry run agentc | grep -q "The Couchbase Agent Catalog command line tool."; then
  echo "Agent Catalog has been installed successfully."
else
  echo "Agent Catalog has not been correctly installed."
  exit 1
fi