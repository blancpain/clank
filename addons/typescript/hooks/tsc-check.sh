#!/bin/bash
# PostToolUse hook: tsc --noEmit project-wide on TS/TSX edits. Opt-in because a full
# project type-check is expensive. Debounced so rapid edits only trigger once per window.
# Bails silently if tsc isn't installed, so safe to leave wired on non-TS projects.

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_response.filePath // empty')

# Only fire on TS/TSX files
if [[ ! "$FILE_PATH" =~ \.(ts|tsx|mts|cts)$ ]]; then
  exit 0
fi

# Skip if file doesn't exist (deleted)
if [[ ! -f "$FILE_PATH" ]]; then
  exit 0
fi

# Resolve project root from the script's location (.claude/hooks/ -> project root)
PROJECT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"

# Find tsc binary: local node_modules -> frontend/node_modules -> PATH -> bail silently
TSC=""
if [[ -x "$PROJECT_DIR/node_modules/.bin/tsc" ]]; then
  TSC="$PROJECT_DIR/node_modules/.bin/tsc"
elif [[ -x "$PROJECT_DIR/frontend/node_modules/.bin/tsc" ]]; then
  TSC="$PROJECT_DIR/frontend/node_modules/.bin/tsc"
elif command -v tsc &>/dev/null; then
  TSC="tsc"
else
  exit 0
fi

DEBOUNCE_SECS=30
MARKER="/tmp/.claude-tsc-check-ts"
if [ -f "$MARKER" ]; then
  NOW=$(date +%s)
  MOD=$(stat -f %m "$MARKER" 2>/dev/null || stat -c %Y "$MARKER" 2>/dev/null)
  if [ -n "$MOD" ]; then
    AGE=$((NOW - MOD))
    if [ "$AGE" -lt "$DEBOUNCE_SECS" ]; then
      exit 0
    fi
  fi
fi
touch "$MARKER"

# Detect tsconfig location: root or frontend/
if [[ -f "$PROJECT_DIR/frontend/tsconfig.json" ]]; then
  CHECK_DIR="$PROJECT_DIR/frontend"
elif [[ -f "$PROJECT_DIR/tsconfig.json" ]]; then
  CHECK_DIR="$PROJECT_DIR"
else
  exit 0
fi

CHECK_OUTPUT=$(cd "$CHECK_DIR" && "$TSC" --noEmit --pretty false 2>&1)
CHECK_EXIT=$?

if [ $CHECK_EXIT -eq 0 ]; then
  exit 0
fi

# Keep output bounded — long type-error dumps flood the context
ERRORS=$(echo "$CHECK_OUTPUT" | head -60)

jq -n \
  --arg errors "$ERRORS" \
  '{
    decision: "block",
    reason: ("tsc found type errors:\n" + $errors + "\nPlease fix these type errors.")
  }'
exit 0
