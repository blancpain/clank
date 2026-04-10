# Authoring hooks

## Hook lifecycle events

Claude Code fires hooks at five points in its execution lifecycle:

| Event | When it fires | Common use |
|-------|---------------|------------|
| `PreToolUse` | Before Claude executes a tool call | Validate the command; block destructive operations |
| `PostToolUse` | After Claude executes a tool call | Lint the file that was just edited; check the output |
| `Stop` | When Claude is about to stop responding | Remind Claude to run reviews before finishing |
| `SubagentStop` | When a subagent finishes | Enforce subagent-level review discipline |
| `UserPromptSubmit` | When the user submits a message | Pre-process or validate user input |

Hooks are shell scripts (or any executable) wired into `settings.json` via a `matcher` that targets specific tools or events.

---

## Exit code semantics

The exit code controls what happens to the tool call:

| Exit code | Meaning | Effect |
|-----------|---------|--------|
| `0` | Pass | Tool call proceeds normally |
| `1` | Warn | stderr is shown to the user; tool call proceeds after user approval |
| `2` | Block | stderr is shown to the model; tool call is prevented |

**JSON decision output** (PostToolUse only): instead of using exit codes, emit a JSON decision to stdout with `exit 0`. This lets the model react and fix issues rather than just being blocked:

```bash
if [[ -n "$ERRORS" ]]; then
  jq -n --arg errors "$ERRORS" '{
    decision: "block",
    reason: ("ruff found issues:\n" + $errors + "\nPlease fix these issues.")
  }'
fi
exit 0
```

Use JSON decision output for linters — the model sees the errors and can fix them in the next turn. Use `exit 2` for hard safety blocks (destructive SQL, rm commands) where you want the model to stop, not fix.

---

## Reading hook input

Claude Code delivers the hook context as JSON on stdin. Read it into a variable at the top of every hook:

```bash
INPUT=$(cat 2>/dev/null) || exit 0
[ -z "$INPUT" ] && exit 0
```

Extract the tool input command with `jq`:

```bash
COMMAND=$(printf '%s' "$INPUT_SAFE" | jq -r '.tool_input.command // empty' 2>/dev/null) || exit 0
```

For PostToolUse hooks on file edits, extract the file path:

```bash
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_response.filePath // empty')
```

---

## Sanitizing input

JSON strings in the hook input may contain literal newlines (e.g. multi-line shell commands). These break `jq` parsing. Always sanitize before passing to `jq`:

```bash
INPUT_SAFE=$(printf '%s' "$INPUT" | tr '\n\r\t' '   ')
COMMAND=$(printf '%s' "$INPUT_SAFE" | jq -r '.tool_input.command // empty' 2>/dev/null) || exit 0
```

The `tr '\n\r\t' '   '` replaces literal newlines, carriage returns, and tabs with spaces, which keeps the JSON parseable without changing the logical content for pattern matching.

---

## Path-flexible tool detection

Hooks must not assume the tool is on `$PATH`. Projects use virtual environments, `uv`, or system installs. The ruff hook shows the full pattern:

```bash
PROJECT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"

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
  exit 0  # bail silently — tool not installed
fi
```

Search order: project-local venv → system-local venv → `uv run` (if `pyproject.toml` present) → `$PATH`. Bail silently with `exit 0` if nothing is found. Never fail loudly when the tool is simply not installed.

---

## Bailing gracefully

A hook must exit 0 when its required tool is absent. This is what allows clank to be installed on projects that don't use a particular language — the hooks are there but inert.

The bash-safety hook does this for `jq`:

```bash
# Bail silently if jq isn't available
command -v jq >/dev/null 2>&1 || exit 0
```

Apply the same pattern to any tool your hook depends on. The rule: **never error on a missing optional tool**. Only hard-block on actual detected problems.

---

## Writing settings fragments

Each hook ships a `settings.fragments/<hook-id>.json` that wires it into the correct lifecycle event and matcher. The installer merges this into the target's `settings.json`.

Fragment for a PreToolUse Bash hook (`base/settings.fragments/bash-safety.json`):

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/pretooluse-bash-safety.sh",
            "statusMessage": "Bash safety checks..."
          }
        ]
      }
    ]
  }
}
```

Fragment for a PostToolUse Edit/Write hook (`addons/python/settings.fragments/ruff.json`):

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/ruff-check.sh",
            "statusMessage": "Running ruff..."
          }
        ]
      }
    ]
  }
}
```

Key points:
- `$CLAUDE_PROJECT_DIR` is the target project root, set by Claude Code at runtime.
- `matcher` is a regex matched against the tool name: `"Bash"`, `"Edit|Write"`, `"mcp__postgres__query"`.
- `statusMessage` is shown in the Claude Code UI while the hook runs.
- The fragment file must be valid JSON. The installer validates it at lint time.

---

## Testing hooks

Test a hook manually by piping JSON on stdin and checking the exit code:

```bash
# Test a PreToolUse Bash hook
echo '{"tool_input":{"command":"DROP TABLE users"}}' | ./base/hooks/pretooluse-bash-safety.sh; echo "exit: $?"

# Test a PostToolUse file hook
echo '{"tool_input":{"file_path":"main.py"}}' | ./addons/python/hooks/ruff-check.sh; echo "exit: $?"
```

For JSON decision output, also check stdout:

```bash
echo '{"tool_input":{"file_path":"badly_formatted.py"}}' | ./addons/python/hooks/ruff-check.sh
# Should print: {"decision":"block","reason":"ruff found issues:\n..."}
```

---

## Common pitfalls

**Forgetting `chmod +x`.** The installer sets the executable bit on hooks automatically after copying. But if you test locally from the clank repo, you must set it manually: `chmod +x base/hooks/my-hook.sh`.

**Using Bash-specific syntax in a `#!/bin/sh` shebang.** The bash-safety hook uses `#!/bin/bash` and relies on Bash-specific features (`[[`, `$'...'`). If you need portability, use `#!/bin/sh` and POSIX syntax only. Pick one and be consistent.

**Grepping without `-E` for extended regex.** `grep -qE 'pat1|pat2'` requires `-E`. Without it, `|` is a literal character.

**Not sanitizing input before `jq`.** Multi-line shell commands in JSON strings will cause `jq` to produce an error, and your hook will likely exit 0 (pass) silently instead of running its checks. Always run `tr '\n\r\t' '   '` before `jq`.

**Not adding the manifest entry.** A hook file with no `[[artifacts]]` entry in `manifest.toml` is invisible to the installer and won't be copied or have its fragment merged. Add both the artifact entry and the `settings_fragment` field.
