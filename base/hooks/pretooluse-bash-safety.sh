#!/bin/bash
# PreToolUse hook: safety checks on Bash commands
# Exit 0 = pass, Exit 2 = block (stderr to model), Exit 1 = warn (stderr to user)

# Bail silently if jq isn't available
command -v jq >/dev/null 2>&1 || exit 0

INPUT=$(cat 2>/dev/null) || exit 0
[ -z "$INPUT" ] && exit 0

# Sanitize input: literal newlines in JSON string values break jq parsing.
# Replace raw control characters with spaces so jq can parse the JSON.
INPUT_SAFE=$(printf '%s' "$INPUT" | tr '\n\r\t' '   ')
COMMAND=$(printf '%s' "$INPUT_SAFE" | jq -r '.tool_input.command // empty' 2>/dev/null) || exit 0
[ -z "$COMMAND" ] && exit 0

# --- PRE-PUSH REMINDER (exit 1 — warn, tool call proceeds after user approval) ---

if echo "$COMMAND" | grep -qE 'git[[:space:]]+push' && ! echo "$COMMAND" | grep -qE '(--delete|-d[[:space:]]|--tags[[:space:]]*$|--dry-run)'; then
  echo "WARNING: BEFORE PUSHING: Have you (1) run the code-reviewer agent and fixed all should-fix findings, and (2) run /simplify on changed code? Do NOT push without completing both steps." >&2
  exit 1
fi

# Skip remaining checks for git commands (commit messages may contain SQL keywords like DELETE)
if echo "$COMMAND" | grep -qE '^git[[:space:]]+(add|commit|status|log|diff|stash|branch|checkout|merge|rebase|cherry-pick|tag|show|blame|bisect|fetch|pull|reset|revert|clean|worktree|remote)'; then
  exit 0
fi

# --- BLOCK RULES (exit 2 — shown to model, tool call prevented) ---
# NOTE: exit 2 blocks are enforced even for auto-allowed commands.
# exit 1 warns are auto-approved for allowed commands — use exit 2 for anything destructive.

# Flatten newlines for SQL checks (multi-line SQL in heredocs/python would bypass line-by-line grep)
COMMAND_FLAT=$(printf '%s' "$COMMAND" | tr '\n' ' ')

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

# --- WARN RULES (exit 1 — shown to user, tool call proceeds) ---
# NOTE: exit 1 warns are auto-approved for auto-allowed commands.
# Only use exit 1 for non-destructive warnings where auto-approval is acceptable.

# Warn: tmux for long-running commands
if echo "$COMMAND" | grep -qE '(npm[[:space:]]+run|pnpm[[:space:]]|yarn[[:space:]]|cargo[[:space:]]|pytest)'; then
  echo "WARNING: Long-running command detected. Consider using a tmux session so the process survives disconnects." >&2
  exit 1
fi

exit 0
