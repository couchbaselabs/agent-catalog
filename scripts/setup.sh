#!/bin/bash

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 {user|dev} "
  exit 1

elif [ "$1" != "user" ] && [ "$1" != "dev" ]; then
  echo "Invalid argument: $1"
  echo "Usage: $0 {user|dev}"
  exit 1
fi

LINE_LENGTH=$(tput cols)
print_separator() {
  local char="$1"
  printf '%*s\n' "$LINE_LENGTH" '' | tr ' ' "$char"
}

print_separator '='
echo "Running scripts/setup.sh"
print_separator '-'

# Install our dependencies with Poetry.
if [ "$1" == "user" ]; then
  poetry install
else
  poetry install --with docs --with dev

  # Get the directory of this script (only used for dev-mode).
  SCRIPT_DIRECTORY=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
  echo "Using script directory: $SCRIPT_DIRECTORY"
  mkdir -p "$SCRIPT_DIRECTORY/../libs/agentc_testing/agentc_testing/resources/models"
  poetry run python "$SCRIPT_DIRECTORY/../libs/agentc_testing/scripts/download_model.py"
fi

# Verify that Agent Catalog is correctly installed.
# (note: the weird `sed` is for stripping ANSI codes for color and formatting).
AGENTC_OUTPUT=$(poetry run agentc 2>&1)
if echo "$AGENTC_OUTPUT" | sed 's/\x1b\[[0-9;]*m//g' | grep -q "The Couchbase Agent Catalog command line tool."; then
  echo "Agent Catalog has been installed successfully."
else
  echo "Agent Catalog has not been correctly installed."
  echo "Error output:"
  echo "$AGENTC_OUTPUT"
  exit 1
fi
print_separator '-'
echo
