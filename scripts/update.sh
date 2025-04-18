#!/bin/bash

LINE_LENGTH=$(tput cols)
print_separator() {
  local char="$1"
  printf '%*s\n' "$LINE_LENGTH" '' | tr ' ' "$char"
}

print_separator '='
echo "Running scripts/update.sh"
print_separator '-'
poetry update
pre-commit run --all-files
print_separator '='
echo
