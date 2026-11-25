#!/bin/bash
# PreToolUse hook: safety checks on Bash commands
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

# Sanitize input: literal newlines in JSON string values break jq parsing.
# Replace raw control characters with spaces so jq can parse the JSON.
INPUT_SAFE=$(printf '%s' "$INPUT" | tr '\n\r\t' '   ')
COMMAND=$(printf '%s' "$INPUT_SAFE" | jq -r '.tool_input.command // empty' 2>/dev/null) || exit 0
[ -z "$COMMAND" ] && exit 0

# Flatten newlines for SQL checks (multi-line SQL in heredocs/python would bypass line-by-line grep)
COMMAND_FLAT=$(printf '%s' "$COMMAND" | tr '\n' ' ')

# Commit messages legitimately mention SQL keywords and `rm`, so the block
# rules are skipped when EVERY segment of the command is a plain git
# subcommand. Quoted strings are dropped first so separators inside a commit
# message don't split it; a chained non-git command (`git add . && rm -rf x`)
# is still checked.
NON_GIT_SEGMENTS=$(printf '%s' "$COMMAND" | tr '\n' ';' \
  | sed -E "s/\"[^\"]*\"//g; s/'[^']*'//g" \
  | tr ';&|(`' '\n\n\n\n\n' \
  | grep -vE '^[[:space:]]*$' \
  | grep -vE '^[[:space:]]*git[[:space:]]+(add|commit|status|log|diff|stash|branch|checkout|merge|rebase|cherry-pick|tag|show|blame|bisect|fetch|pull|push|reset|revert|clean|worktree|remote)([[:space:]]|$)')

# --- BLOCK RULES (exit 2 — shown to model, tool call prevented) ---
# NOTE: exit 2 blocks are enforced even for auto-allowed commands.

if [ -n "$NON_GIT_SEGMENTS" ]; then
  # Block destructive SQL (DROP TABLE/COLUMN/SCHEMA/INDEX, TRUNCATE, DELETE)
  if echo "$COMMAND_FLAT" | grep -qiE "(DROP[[:space:]]+(TABLE|COLUMN|SCHEMA|INDEX|DATABASE|VIEW|FUNCTION|TRIGGER|SEQUENCE|TYPE)|TRUNCATE|DELETE[[:space:]]+FROM)"; then
    cat >&2 <<'EOF'
BLOCKED: Destructive SQL detected (DROP/TRUNCATE/DELETE).
Ask the user before proceeding. If approved, the user can run it manually.
EOF
    exit 2
  fi

  # Block UPDATE statements (data mutation — must have explicit user approval)
  if echo "$COMMAND_FLAT" | grep -qiE "UPDATE[[:space:]]+(\"[^\"]+\"|[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)?)[[:space:]]+(([a-zA-Z_][a-zA-Z0-9_]*|AS[[:space:]]+[a-zA-Z_][a-zA-Z0-9_]*)[[:space:]]+)?SET[[:space:]]"; then
    cat >&2 <<'EOF'
BLOCKED: UPDATE statement detected.
Ask the user for explicit approval before running data mutations.
Write the mutation logic to a reviewable script instead of running UPDATE directly.
EOF
    exit 2
  fi

  # Block rm / rm -rf (includes subshell forms like $(rm ...) and `rm ...`)
  if echo "$COMMAND_FLAT" | grep -qE '(^|[;&|([:space:]`])rm[[:space:]]'; then
    cat >&2 <<'EOF'
BLOCKED: rm command detected.
File deletion requires explicit user approval. Ask the user before proceeding.
EOF
    exit 2
  fi
fi

# --- ASK RULES (exit 0 + JSON — forces a user permission prompt) ---
# Runs after the block rules so a push chained with something destructive is
# still blocked. The reason is shown to the user in the prompt.

if echo "$COMMAND" | grep -qE 'git[[:space:]]+push' && ! echo "$COMMAND" | grep -qE '(--delete|-d[[:space:]]|--tags[[:space:]]*$|--dry-run)'; then
  jq -n '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "ask",
      permissionDecisionReason: "git push publishes these commits. Approve only if the code-reviewer findings on this diff have been addressed."
    }
  }'
  exit 0
fi

exit 0
