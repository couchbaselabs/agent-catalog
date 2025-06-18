#!/bin/bash

LINE_LENGTH=$(tput cols)
print_separator() {
  local char="$1"
  printf '%*s\n' "$LINE_LENGTH" '' | tr ' ' "$char"
}

print_separator '='
echo "Running scripts/post-build.sh"
print_separator '-'

# Note: dynamic-versioning and monoranger does not play well with each other :-(.
echo "Restoring .toml and __init__ files."
FILES=(
  pyproject.toml
  libs/agentc/pyproject.toml
  libs/agentc/agentc/__init__.py
  libs/agentc_core/pyproject.toml
  libs/agentc_core/agentc_core/__init__.py
  libs/agentc_cli/pyproject.toml
  libs/agentc_cli/agentc_cli/__init__.py
  libs/agentc_integrations/langchain/pyproject.toml
  libs/agentc_integrations/langchain/agentc_langchain/__init__.py
  libs/agentc_integrations/langgraph/pyproject.toml
  libs/agentc_integrations/langgraph/agentc_langgraph/__init__.py
  libs/agentc_integrations/llamaindex/pyproject.toml
  libs/agentc_integrations/llamaindex/agentc_llamaindex/__init__.py
  libs/agentc_testing/pyproject.toml
  libs/agentc_testing/agentc_testing/__init__.py
)
for file in "${FILES[@]}"; do
  mv dist/temp/"$file".bak "$file"
done

print_separator '-'
