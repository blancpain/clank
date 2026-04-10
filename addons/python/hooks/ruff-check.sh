#!/bin/bash
# PostToolUse hook: run ruff on edited Python files
# Returns decision:block with errors if ruff fails so Claude fixes them.
#
# Searches for ruff in: ./venv/bin/ruff, ./.venv/bin/ruff, uv run ruff, $PATH.
# Bails silently if none are available.

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_response.filePath // empty')

if [[ ! "$FILE_PATH" =~ \.py$ ]]; then
  exit 0
fi

if [[ ! -f "$FILE_PATH" ]]; then
  exit 0
fi

PROJECT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"

# Resolve a ruff binary
RUFF=""
if [[ -x "$PROJECT_DIR/.venv/bin/ruff" ]]; then
  RUFF="$PROJECT_DIR/.venv/bin/ruff"
elif [[ -x "$PROJECT_DIR/venv/bin/ruff" ]]; then
  RUFF="$PROJECT_DIR/venv/bin/ruff"
elif command -v uv >/dev/null 2>&1 && [[ -f "$PROJECT_DIR/pyproject.toml" ]]; then
  RUFF="uv run ruff"
elif command -v ruff >/dev/null 2>&1; then
  RUFF="ruff"
fi

if [[ -z "$RUFF" ]]; then
  exit 0
fi

ERRORS=""
if ! LINT_OUTPUT=$($RUFF check "$FILE_PATH" 2>&1); then
  ERRORS="$LINT_OUTPUT"
fi
if ! FMT_OUTPUT=$($RUFF format --check "$FILE_PATH" 2>&1); then
  ERRORS="${ERRORS:+$ERRORS\n}$FMT_OUTPUT"
fi

if [[ -n "$ERRORS" ]]; then
  jq -n --arg errors "$ERRORS" '{
    decision: "block",
    reason: ("ruff found issues:\n" + $errors + "\nPlease fix these issues.")
  }'
fi
exit 0
