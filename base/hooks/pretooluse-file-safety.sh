#!/bin/bash
# PreToolUse hook: safety checks on file edits (Edit/Write)
# Exit 0 = pass, Exit 2 = block (stderr to model)
#
# Edit the FILE_PATTERNS and FORBIDDEN_PATTERNS variables at the top to
# customize which files trigger which DDL blocks for this project.

# --- CONFIG ---
# Extended regex matched against the file_path being written/edited.
# Files matching this pattern will be checked for forbidden content.
FILE_PATTERNS='(schema|migration|migrations|\.sql$)'

# Extended regex matched against the content (new_string or content field).
# If the content matches AND the file matches FILE_PATTERNS, the write is blocked.
FORBIDDEN_PATTERNS='(DROP[[:space:]]+TABLE|DROP[[:space:]]+COLUMN|TRUNCATE|DELETE[[:space:]]+FROM)'
# --- END CONFIG ---

# Bail silently if jq isn't available
command -v jq >/dev/null 2>&1 || exit 0

INPUT=$(cat 2>/dev/null) || exit 0
[ -z "$INPUT" ] && exit 0

# Sanitize: literal newlines in JSON string values break jq parsing
INPUT_SAFE=$(printf '%s' "$INPUT" | tr '\n\r\t' '   ')
FILE_PATH=$(printf '%s' "$INPUT_SAFE" | jq -r '.tool_input.file_path // empty' 2>/dev/null) || exit 0
[ -z "$FILE_PATH" ] && exit 0

# Check if the file matches our pattern
if echo "$FILE_PATH" | grep -qE "$FILE_PATTERNS"; then
  NEW_TEXT=$(printf '%s' "$INPUT_SAFE" | jq -r '.tool_input.new_string // .tool_input.content // empty')
  if echo "$NEW_TEXT" | grep -qiE "$FORBIDDEN_PATTERNS"; then
    cat >&2 <<'EOF'
BLOCKED: Destructive DDL detected in a schema/migration file.

Adding DROP TABLE/DROP COLUMN/TRUNCATE/DELETE FROM to schema or migration
files is forbidden. This prevents accidental data loss if migrations
re-execute on startup.

Rules:
- NEVER add destructive DDL to schema DDL or MIGRATIONS arrays
- If truly needed, run as a standalone one-off script
- Always get explicit user approval first
EOF
    exit 2
  fi
fi

exit 0
