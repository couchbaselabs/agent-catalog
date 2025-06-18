#!/bin/bash

LINE_LENGTH=$(tput cols)
print_separator() {
  local char="$1"
  printf '%*s\n' "$LINE_LENGTH" '' | tr ' ' "$char"
}

print_separator '='
echo "Running scripts/build.sh"
print_separator '-'

# Our core packages (core, CLI, and agentc) need to be built.
mkdir -p dist
for package in agentc_core agentc_cli agentc; do
  echo "Building '$package' package..."
  cd "libs/$package" || exit
  poetry build --format wheel --output ../../dist
  cd ../../
  echo "Package '$package' built!"
done

# Next, our integration packages.
for package in langchain langgraph llamaindex; do
  echo "Building '$package' integration package..."
  cd "libs/agentc_integrations/$package" || exit
  poetry build --format wheel --output ../../../dist
  cd ../../../
  echo "Integration package '$package' built!"
done

print_separator '-'
