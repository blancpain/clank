#!/bin/bash
# PreToolUse hook: block `git commit` once to nudge running code-reviewer first.
# Fires on the Bash tool. The first commit attempt on a code-bearing diff is
# blocked with a reminder; a per-repo marker then lets the *next* commit attempt
# pass through (giving Claude room to run the review, address findings, then
# commit without getting trapped in a re-block loop).
#
# Pairs with the `no-redundant-review` rule, which prevents Claude from
# dispatching the reviewer twice on the same diff after this hook fires.
#
# OPT-IN: default=false in manifest.toml. The installer prompts once.
#
# Edit EXTENSIONS / WINDOW_SECONDS below to tune.

# --- CONFIG ---
EXTENSIONS=".py .ts .tsx .js .jsx .go .rs .svelte .sh .sql"
WINDOW_SECONDS=1800
# --- END CONFIG ---

command -v jq >/dev/null 2>&1 || exit 0

INPUT=$(cat 2>/dev/null) || exit 0
[ -z "$INPUT" ] && exit 0

# Literal newlines in JSON string values break jq parsing; sanitize first.
INPUT_SAFE=$(printf '%s' "$INPUT" | tr '\n\r\t' '   ')
COMMAND=$(printf '%s' "$INPUT_SAFE" | jq -r '.tool_input.command // empty' 2>/dev/null) || exit 0
[ -z "$COMMAND" ] && exit 0

# Only act on `git commit`. Match at word boundaries so subcommands like
# `git commit-tree` aren't caught, and so the command can appear after `&&`,
# `;`, or a leading subshell.
echo "$COMMAND" | grep -qE '(^|[;&|[:space:]`(])git[[:space:]]+commit([[:space:]]|$)' || exit 0

REPO="${CLAUDE_PROJECT_DIR:-$(pwd)}"

# Build extension regex from the config above.
EXT_REGEX=$(echo "$EXTENSIONS" | sed 's/^ *//; s/ *$//; s/  */ /g; s/ /|/g; s/\./\\./g')

# Only block when the staged diff actually contains code we care about.
STAGED_CODE=$(git -C "$REPO" diff --cached --name-only 2>/dev/null | grep -E "($EXT_REGEX)$" || true)
[ -z "$STAGED_CODE" ] && exit 0

# Per-repo marker — different projects must not share state.
REPO_HASH=$(printf '%s' "$REPO" | shasum 2>/dev/null | awk '{print $1}')
[ -z "$REPO_HASH" ] && REPO_HASH=$(printf '%s' "$REPO" | md5 2>/dev/null | awk '{print $NF}')
[ -z "$REPO_HASH" ] && REPO_HASH="default"
MARKER="/tmp/.claude-review-before-commit-$REPO_HASH"

if [ -f "$MARKER" ]; then
  AGE=$(($(date +%s) - $(stat -f %m "$MARKER" 2>/dev/null || stat -c %Y "$MARKER" 2>/dev/null || echo 0)))
  if [ "$AGE" -lt "$WINDOW_SECONDS" ]; then
    exit 0
  fi
  rm -f "$MARKER"
fi

touch "$MARKER"
cat >&2 <<EOF
BLOCKED: git commit attempted on a code-bearing diff without a code review in this session.

Before retrying:
  1. Dispatch the code-reviewer agent (or the language-specific reviewer if one exists)
     on the staged diff and fix all should-fix findings.
  2. If a /simplify skill is available, run it on the changed code.

This hook blocks ONCE per commit window — the next \`git commit\` in this repo will
pass through without re-blocking (within ${WINDOW_SECONDS}s). Do NOT re-dispatch the
reviewer on the same diff after it has already reviewed (see rule: no-redundant-review).
EOF
exit 2
