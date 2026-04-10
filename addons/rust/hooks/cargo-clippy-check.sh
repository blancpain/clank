#!/bin/bash
# PostToolUse hook: run cargo clippy on edited Rust files
# Bails silently if not a Cargo workspace or cargo isn't installed.

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_response.filePath // empty')

if [[ ! "$FILE_PATH" =~ \.rs$ ]]; then
  exit 0
fi
if [[ ! -f "$FILE_PATH" ]]; then
  exit 0
fi

PROJECT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"

if [[ ! -f "$PROJECT_DIR/Cargo.toml" ]]; then
  exit 0
fi
if ! command -v cargo >/dev/null 2>&1; then
  exit 0
fi

if CLIPPY_OUTPUT=$(cd "$PROJECT_DIR" && cargo clippy --workspace --all-targets --quiet -- -D warnings 2>&1); then
  exit 0
else
  jq -n --arg errors "$CLIPPY_OUTPUT" '{
    decision: "block",
    reason: ("cargo clippy found issues:\n" + $errors + "\nPlease fix these issues.")
  }'
fi
exit 0
