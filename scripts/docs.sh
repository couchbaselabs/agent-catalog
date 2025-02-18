#!/bin/bash

LINE_LENGTH=$(tput cols)
printf '%*s\n' "$LINE_LENGTH" '' | tr ' ' '='
echo "Running ./scripts/docs.sh"
printf '%*s\n' "$LINE_LENGTH" '' | tr ' ' '='

# Get the directory of this script.
SCRIPT_DIRECTORY=$(dirname -- "$(readlink -f -- "${BASH_SOURCE[0]}")")
echo "Using script directory: $SCRIPT_DIRECTORY"
cd "$SCRIPT_DIRECTORY/../docs" || exit

# Generate the documentation with Make.
make html

# Serve the documentation with sphinx-autobuild.
sphinx-autobuild source build
