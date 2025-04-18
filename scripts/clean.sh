#!/bin/bash

LINE_LENGTH=$(tput cols)
print_separator() {
  local char="$1"
  printf '%*s\n' "$LINE_LENGTH" '' | tr ' ' "$char"
}

# Check if force has been specified.
if [ "$1" == "--force" ]; then
  FORCE=true
else
  FORCE=false
fi

print_separator '='
echo "Running scripts/clean.sh"
print_separator '-'

eval "$(poetry env activate)"

# Clean up our poetry files.
WORKING_ENVIRONMENT_NAME=$(poetry env list | grep \(Activated\) | cut -f 1 -d ' ')
if [ -n "$WORKING_ENVIRONMENT_NAME" ]; then
  poetry env remove "$WORKING_ENVIRONMENT_NAME"
fi
find . -type f -name "poetry.lock" -exec rm -rv {} +
if [ "$FORCE" = true ]; then
  poetry cache clear pypi --all
fi

# Clean any output directories / files.
find . -type d -name ".agent-activity" -exec rm -rv {} +
find . -type d -name ".agent-catalog" -exec rm -rv {} +
find . -type d -name ".data" -exec rm -rv {} +
find . -type d -name ".model-cache" -exec rm -rv {} +
find docs -type d -name "build" -exec rm -rv {} + 2> /dev/null
find . -type f -name ".output" -exec rm -rv {} +

# If you run into some weird issues with SentenceTransformers, try raising the force flag.
if [ "$FORCE" = true ]; then
  huggingface-cli delete-cache --disable-tui
fi
print_separator '='
echo
