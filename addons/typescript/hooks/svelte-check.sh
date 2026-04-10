#!/bin/bash
# PostToolUse hook: svelte-check on edited .svelte files. Part of the typescript addon —
# inert on non-Svelte projects. Bails silently if svelte-check isn't installed, so safe
# to leave wired on non-Svelte projects.

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_response.filePath // empty')

# Only fire on .svelte files
if [[ ! "$FILE_PATH" =~ \.svelte$ ]]; then
  exit 0
fi

# Skip if file doesn't exist (deleted)
if [[ ! -f "$FILE_PATH" ]]; then
  exit 0
fi

# Resolve project root from the script's location (.claude/hooks/ -> project root)
PROJECT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"

# Find svelte-check binary: local node_modules -> frontend/node_modules -> PATH -> bail silently
SVELTE_CHECK=""
if [[ -x "$PROJECT_DIR/node_modules/.bin/svelte-check" ]]; then
  SVELTE_CHECK="$PROJECT_DIR/node_modules/.bin/svelte-check"
elif [[ -x "$PROJECT_DIR/frontend/node_modules/.bin/svelte-check" ]]; then
  SVELTE_CHECK="$PROJECT_DIR/frontend/node_modules/.bin/svelte-check"
elif command -v svelte-check &>/dev/null; then
  SVELTE_CHECK="svelte-check"
else
  exit 0
fi

DEBOUNCE_SECS=30
MARKER="/tmp/.claude-svelte-check-ts"
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
TSCONFIG_FLAG=""
if [[ -f "$PROJECT_DIR/frontend/tsconfig.json" ]]; then
  CHECK_DIR="$PROJECT_DIR/frontend"
  TSCONFIG_FLAG="--tsconfig ./tsconfig.json"
elif [[ -f "$PROJECT_DIR/tsconfig.json" ]]; then
  CHECK_DIR="$PROJECT_DIR"
  TSCONFIG_FLAG="--tsconfig ./tsconfig.json"
else
  CHECK_DIR="$PROJECT_DIR"
fi

CHECK_OUTPUT=$(cd "$CHECK_DIR" && "$SVELTE_CHECK" $TSCONFIG_FLAG 2>&1)
CHECK_EXIT=$?

if [ $CHECK_EXIT -eq 0 ]; then
  exit 0
fi

# Extract only error lines (skip warnings to reduce noise)
ERRORS=$(echo "$CHECK_OUTPUT" | grep -A2 "^Error:" | head -40)
if [ -z "$ERRORS" ]; then
  ERRORS=$(echo "$CHECK_OUTPUT" | tail -20)
fi

jq -n \
  --arg errors "$ERRORS" \
  '{
    decision: "block",
    reason: ("svelte-check found type errors:\n" + $errors + "\nPlease fix these type errors.")
  }'
exit 0
