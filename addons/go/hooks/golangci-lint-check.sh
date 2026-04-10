#!/bin/bash
# PostToolUse hook: run golangci-lint on edited Go files
# Bails silently if golangci-lint isn't installed or the project isn't a Go module.

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_response.filePath // empty')

if [[ ! "$FILE_PATH" =~ \.go$ ]]; then
  exit 0
fi
if [[ ! -f "$FILE_PATH" ]]; then
  exit 0
fi

PROJECT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"

if [[ ! -f "$PROJECT_DIR/go.mod" ]]; then
  exit 0
fi
if ! command -v golangci-lint >/dev/null 2>&1; then
  exit 0
fi

PKG_DIR="$(dirname "$FILE_PATH")"

if LINT_OUTPUT=$(cd "$PROJECT_DIR" && golangci-lint run "$PKG_DIR/..." 2>&1); then
  exit 0
else
  jq -n --arg errors "$LINT_OUTPUT" '{
    decision: "block",
    reason: ("golangci-lint found issues:\n" + $errors + "\nPlease fix these issues.")
  }'
fi
exit 0
