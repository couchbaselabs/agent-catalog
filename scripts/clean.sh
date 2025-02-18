#!/bin/bash

# Check if force has been specified.
if [ "$1" == "--force" ]; then
  FORCE=true
else
  FORCE=false
fi

LINE_LENGTH=$(tput cols)
printf '%*s\n' "$LINE_LENGTH" '' | tr ' ' '='
echo "Running ./scripts/clean.sh"
printf '%*s\n' "$LINE_LENGTH" '' | tr ' ' '='

eval "$(poetry env activate)"

# Clean any output directories / files.
find . -type d -name ".agent-activity" -exec rm -rv {} +
find . -type d -name ".agent-catalog" -exec rm -rv {} +
find . -type d -name ".data" -exec rm -rv {} +
find . -type d -name ".model-cache" -exec rm -rv {} +
find docs -type d -name "build" -exec rm -rv {} +
find . -type f -name ".output" -exec rm -rv {} +

# If you run into some weird issues with SentenceTransformers, try raising the force flag.
if [ "$FORCE" = true ]; then
  huggingface-cli delete-cache --disable-tui
fi
