#!/bin/bash
# PreToolUse hook: safety checks on MCP postgres queries
# Exit 0 = pass, Exit 2 = block (stderr to model), Exit 1 = warn (stderr to user)

# Bail silently if jq isn't available
command -v jq >/dev/null 2>&1 || exit 0

INPUT=$(cat 2>/dev/null) || exit 0
[ -z "$INPUT" ] && exit 0

# Sanitize: literal newlines in JSON string values break jq parsing
INPUT_SAFE=$(printf '%s' "$INPUT" | tr '\n\r\t' '   ')
SQL=$(printf '%s' "$INPUT_SAFE" | jq -r '.tool_input.query // .tool_input.sql // empty' 2>/dev/null) || exit 0
[ -z "$SQL" ] && exit 0

# Flatten for multi-line SQL
SQL_FLAT=$(printf '%s' "$SQL" | tr '\n' ' ')

# --- BLOCK RULES (exit 2) ---

# Block destructive SQL: DROP/TRUNCATE/DELETE
if echo "$SQL_FLAT" | grep -qiE "(DROP[[:space:]]+(TABLE|COLUMN|SCHEMA|INDEX|DATABASE|VIEW|FUNCTION|TRIGGER|SEQUENCE|TYPE)|TRUNCATE|DELETE[[:space:]]+FROM)"; then
  cat >&2 <<'EOF'
BLOCKED: Destructive SQL detected via MCP postgres (DROP/TRUNCATE/DELETE).
Ask the user before proceeding. If approved, the user can run it manually.
EOF
  exit 2
fi

# Block UPDATE statements (data mutation)
if echo "$SQL_FLAT" | grep -qiE "UPDATE[[:space:]]+(\"[^\"]+\"|[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)?)[[:space:]]+(([a-zA-Z_][a-zA-Z0-9_]*|AS[[:space:]]+[a-zA-Z_][a-zA-Z0-9_]*)[[:space:]]+)?SET[[:space:]]"; then
  cat >&2 <<'EOF'
BLOCKED: UPDATE statement detected via MCP postgres.
Write the mutation logic to a reviewable script. Have the user approve it before running directly against the database.
EOF
  exit 2
fi

# --- WARN RULES (exit 1) ---

# ALTER, INSERT — user must approve
if echo "$SQL_FLAT" | grep -qiE "(ALTER[[:space:]]+TABLE|INSERT[[:space:]]+INTO)"; then
  echo "⚠ SQL WRITE OPERATION via MCP postgres (ALTER/INSERT). You MUST get explicit user approval — do NOT proceed without it." >&2
  exit 1
fi

exit 0
