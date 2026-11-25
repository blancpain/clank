#!/bin/bash
# PreToolUse hook: safety checks on MCP supabase queries and migrations
#
# Exit 2 + stderr         = block; the model sees the reason.
# Exit 0 + JSON on stdout = structured decision ("ask" forces a user prompt).
# Exit 0, no output       = no objection; the normal permission flow applies.
# Any other exit code is a non-blocking hook ERROR: the call proceeds with no
# prompt. Never use one as a "warning".

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
BLOCKED: Destructive SQL detected via MCP supabase (DROP/TRUNCATE/DELETE).
Ask the user before proceeding. If approved, the user can run it manually.
EOF
  exit 2
fi

# Block UPDATE statements (data mutation)
if echo "$SQL_FLAT" | grep -qiE "UPDATE[[:space:]]+(\"[^\"]+\"|[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)?)[[:space:]]+(([a-zA-Z_][a-zA-Z0-9_]*|AS[[:space:]]+[a-zA-Z_][a-zA-Z0-9_]*)[[:space:]]+)?SET[[:space:]]"; then
  cat >&2 <<'EOF'
BLOCKED: UPDATE statement detected via MCP supabase.
Write the mutation logic to a reviewable script. Have the user approve it before running directly against the database.
EOF
  exit 2
fi

# --- ASK RULES (exit 0 + JSON — forces a user permission prompt) ---

# ALTER, INSERT — user must approve
if echo "$SQL_FLAT" | grep -qiE "(ALTER[[:space:]]+TABLE|INSERT[[:space:]]+INTO)"; then
  jq -n '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "ask",
      permissionDecisionReason: "SQL write (ALTER/INSERT) via MCP supabase. Approve only if you want this change applied to the database."
    }
  }'
  exit 0
fi

exit 0
