#!/bin/bash

LINE_LENGTH=$(tput cols)
print_separator() {
  local char="$1"
  printf '%*s\n' "$LINE_LENGTH" '' | tr ' ' "$char"
}

print_separator '='
echo "Running scripts/activate.sh"
print_separator '-'

echo "To activate your virtual environment, copy and paste the command below into your shell: "
poetry env activate
print_separator '='
echo
