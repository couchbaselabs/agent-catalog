#!/bin/bash

LINE_LENGTH=$(tput cols)
print_separator() {
  local char="$1"
  printf '%*s\n' "$LINE_LENGTH" '' | tr ' ' "$char"
}

print_separator '='
echo "Running scripts/publish.sh"
print_separator '-'

# # Uncomment the lines below to publish to a private PyPI repository (e.g., devpi).
# # Also, uncomment the "-r cb" flag in the `poetry publish` commands.
# poetry config repositories.cb "http://localhost:3141/$USERNAME/$INDEX_NAME"
# poetry config http-basic.cb "$USERNAME" "$PASSWORD"

# First, our core packages (core, CLI, and agentc) need to be published.
for package in agentc_core agentc_cli agentc; do
  echo "Publishing '$package' package..."
  cd "libs/$package" || exit
  poetry build
  poetry publish # -r cb
  cd ../../
  echo "Package '$package' published!"
done

# Next, our integration packages.
for package in langchain langgraph llamaindex; do
  echo "Publishing '$package' integration package..."
  cd "libs/agentc_integrations/$package" || exit
  poetry build
  poetry publish # -r cb
  cd ../../../
  echo "Integration package '$package' published!"
done

print_separator '-'
