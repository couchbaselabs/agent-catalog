#!/bin/bash

LINE_LENGTH=$(tput cols)
print_separator() {
  local char="$1"
  printf '%*s\n' "$LINE_LENGTH" '' | tr ' ' "$char"
}

print_separator '='
echo "Running scripts/pre-build.sh"
print_separator '-'

# Note: dynamic-versioning and monoranger does not play well with each other :-(.
echo "Creating backups of .toml and __init__ files."
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
  cp "$file" dist/temp/"$file".bak
done

echo "Modifying file versions."
PDV_OUTPUT=$(poetry dynamic-versioning 2>&1 1>/dev/null)
VERSION=$(echo "$PDV_OUTPUT" | grep -m 1 '^Version' | awk '{print $2}')
echo "Using version ${VERSION} from PDV output ${PDV_OUTPUT}."
if [[ "$(uname)" == "Darwin" ]]; then
  SED_INPLACE=(-i '')
else
  SED_INPLACE=(-i)
fi
find libs -type f -name 'pyproject.toml' \
  -exec sed "${SED_INPLACE[@]}" \
   "s/version = \"0.0.0\"/version = \"$VERSION\"/g" {} +

print_separator '-'
