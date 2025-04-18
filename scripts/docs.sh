#!/bin/bash

LINE_LENGTH=$(tput cols)
print_separator() {
  local char="$1"
  printf '%*s\n' "$LINE_LENGTH" '' | tr ' ' "$char"
}

print_separator '='
echo "Running scripts/docs.sh"
print_separator '-'

# Get the directory of this script.
SCRIPT_DIRECTORY=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
echo "Using script directory: $SCRIPT_DIRECTORY"
cd "$SCRIPT_DIRECTORY/../docs" || exit

# Generate the documentation with Make.
make html

# Serve the documentation with sphinx-autobuild.
sphinx-autobuild source build
print_separator '='
echo
