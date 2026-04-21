#!/bin/bash
# PostToolUse hook: run eslint on edited TS/JS files
# Returns decision:block with errors if eslint fails, so Claude fixes them

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_response.filePath // empty')

# Only fire on TS/JS files
if [[ ! "$FILE_PATH" =~ \.(ts|tsx|js|jsx|mjs|cjs)$ ]]; then
  exit 0
fi

# Skip if file doesn't exist (deleted)
if [[ ! -f "$FILE_PATH" ]]; then
  exit 0
fi

# Resolve project root from the script's location (.claude/hooks/ -> project root)
PROJECT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"

# Find eslint binary: local node_modules -> frontend/node_modules -> PATH -> bail silently
ESLINT=""
if [[ -x "$PROJECT_DIR/node_modules/.bin/eslint" ]]; then
  ESLINT="$PROJECT_DIR/node_modules/.bin/eslint"
elif [[ -x "$PROJECT_DIR/frontend/node_modules/.bin/eslint" ]]; then
  ESLINT="$PROJECT_DIR/frontend/node_modules/.bin/eslint"
elif command -v eslint &>/dev/null; then
  ESLINT="eslint"
else
  exit 0
fi

if ESLINT_OUTPUT=$(cd "$PROJECT_DIR" && "$ESLINT" "$FILE_PATH" 2>&1); then
  exit 0
else
  jq -n \
    --arg errors "$ESLINT_OUTPUT" \
    '{
      decision: "block",
      reason: ("eslint found issues:\n" + $errors + "\nPlease fix these issues.")
    }'
  exit 0
fi
