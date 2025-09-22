#!/bin/bash

LINE_LENGTH=$(tput cols)
print_separator() {
  local char="$1"
  printf '%*s\n' "$LINE_LENGTH" '' | tr ' ' "$char"
}

print_separator '='
echo "Running scripts/pre-setup.sh"
print_separator '-'

# Check #1: Python must exist.
if ! [ -x "$(command -v python)" ]; then
  echo "Python is not installed. Please install Python 3.11 and try again."
  echo "You can download Python from https://www.python.org/downloads/"
  exit 1
fi

# Check #2: The Python version must be 3.11.
if [ "$(python -c 'import sys; print(sys.version_info >= (3, 11))')" != "True" ]; then
  echo "Python >=3.11 is required, but found $(python --version). Please install Python 3.11 and try again."
  echo "You can download Python from https://www.python.org/downloads/"
  exit 1
fi

# Check #3: Poetry must exist.
if ! [ -x "$(command -v poetry)" ]; then
  echo "Poetry is not installed. Please install Poetry and try again."
  echo "You can install Poetry by running 'pipx install poetry' or 'pip install poetry'."
  exit 1
fi

print_separator '='
echo
