#!/bin/bash
# Stop hook: remind to run code review + simplify before completing
# Uses JSON {decision: "block"} on stdout with exit 0
# Marker file prevents infinite loop: first attempt blocks, second allows
#
# OPT-IN: This hook is excluded from @tag:* and @preset:* expansion by default
# (default=false in manifest.toml). The installer prompts once before enabling it.
#
# Edit EXTENSIONS at the top to control which file types trigger the reminder.

# --- CONFIG ---
# Space-separated list of file extensions to watch for code changes.
# The reminder fires when any changed/staged/untracked file matches these extensions.
EXTENSIONS=".py .ts .tsx .js .jsx .go .rs .svelte .sh .sql"
# --- END CONFIG ---

# Build grep regex dynamically from EXTENSIONS
EXT_REGEX=$(echo "$EXTENSIONS" | sed 's/^ *//; s/ *$//; s/  */ /g; s/ /|/g; s/\./\\./g')

# Consume stdin
cat >/dev/null 2>&1

# Bail if jq not available
command -v jq >/dev/null 2>&1 || exit 0

MARKER="/tmp/.claude-stop-review-reminder"

# If marker exists and is recent (<120s), allow stop (prevents infinite loop)
if [ -f "$MARKER" ]; then
  AGE=$(($(date +%s) - $(stat -f %m "$MARKER" 2>/dev/null || stat -c %Y "$MARKER" 2>/dev/null || echo 0)))
  if [ "$AGE" -lt 120 ]; then
    exit 0
  fi
  rm -f "$MARKER"
fi

# Check for code changes
REPO="${CLAUDE_PROJECT_DIR:-.}"
CODE_CHANGES=$(git -C "$REPO" diff --name-only HEAD 2>/dev/null | grep -E "($EXT_REGEX)$" || true)
STAGED_CODE=$(git -C "$REPO" diff --cached --name-only 2>/dev/null | grep -E "($EXT_REGEX)$" || true)
UNTRACKED=$(git -C "$REPO" ls-files --others --exclude-standard 2>/dev/null | grep -E "($EXT_REGEX)$" || true)

if [ -n "$CODE_CHANGES" ] || [ -n "$STAGED_CODE" ] || [ -n "$UNTRACKED" ]; then
  touch "$MARKER"
  jq -n '{
    decision: "block",
    reason: "Code changes detected. Before completing: (1) Run the code-reviewer agent and fix all should-fix findings. (2) If available, run /simplify on changed code. If already done, you may proceed."
  }'
  exit 0
fi

exit 0
