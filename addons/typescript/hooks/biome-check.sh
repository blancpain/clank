#!/bin/bash
# PostToolUse hook: run biome on edited TS/JS/Svelte files
# Returns decision:block with errors if biome fails, so Claude fixes them

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_response.filePath // empty')

# Only fire on TS/JS/Svelte/JSX files
if [[ ! "$FILE_PATH" =~ \.(svelte|ts|tsx|js|jsx|mjs|cjs)$ ]]; then
  exit 0
fi

# Skip if file doesn't exist (deleted)
if [[ ! -f "$FILE_PATH" ]]; then
  exit 0
fi

# Resolve project root from the script's location (.claude/hooks/ -> project root)
PROJECT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"

# Find biome binary: local node_modules -> frontend/node_modules -> PATH -> bail silently
BIOME=""
if [[ -x "$PROJECT_DIR/node_modules/.bin/biome" ]]; then
  BIOME="$PROJECT_DIR/node_modules/.bin/biome"
elif [[ -x "$PROJECT_DIR/frontend/node_modules/.bin/biome" ]]; then
  BIOME="$PROJECT_DIR/frontend/node_modules/.bin/biome"
elif command -v biome &>/dev/null; then
  BIOME="biome"
else
  exit 0
fi

if BIOME_OUTPUT=$(cd "$PROJECT_DIR" && "$BIOME" check "$FILE_PATH" 2>&1); then
  exit 0
else
  jq -n \
    --arg errors "$BIOME_OUTPUT" \
    '{
      decision: "block",
      reason: ("biome found issues:\n" + $errors + "\nPlease fix these issues.")
    }'
  exit 0
fi
