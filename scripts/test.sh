#!/bin/bash

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 {smoke|click|slow} "
  exit 1

elif [ "$1" != "smoke" ] && [ "$1" != "click" ] && [ "$1" != "slow" ]; then
  echo "Invalid argument: $1"
  echo "Usage: $0 {smoke|click|slow} "
  exit 1
fi

LINE_LENGTH=$(tput cols)
print_separator() {
  local char="$1"
  printf '%*s\n' "$LINE_LENGTH" '' | tr ' ' "$char"
}

print_separator '='
echo "Running scripts/test.sh"
print_separator '-'

if [ "$1" == "smoke" ]; then
  poetry run bash -c "pytest -m smoke -v --log-level DEBUG"

elif [ "$1" == "click" ]; then
  poetry run bash -c "pytest libs/agentc_cli -v --retries 3 --retry-delay 300"

elif [ "$1" == "slow" ]; then
  poetry run bash -c "pytest -m slow -v --retries 3 --retry-delay 300 --ignore-glob=*agentc_cli*"
fi

print_separator '-'
echo