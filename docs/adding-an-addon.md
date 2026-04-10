# Adding a language addon

This guide walks through adding a new language addon from scratch, using `addons/python/` as the worked example. By the end you will have a new preset that users can install with `--preset <lang>`.

---

## What an addon is

An addon is a directory under `addons/<lang>/` that mirrors the `base/` layout. It ships language-specific artifacts: a specialist reviewer agent, a lint/format hook, rules covering style/testing/security/patterns, and optionally skills. When a user installs the `<lang>` preset, they get `base-only` plus everything in the addon.

Addon artifacts are installed into the same `<target>/.claude/` locations as base artifacts. `addons/python/agents/python-reviewer.md` lands at `<target>/.claude/agents/python-reviewer.md`. The installer strips the `addons/<name>/` prefix automatically.

---

## Addon directory layout

```
addons/<lang>/
    agents/
        <lang>-reviewer.md
    hooks/
        <lang>-check.sh
    rules/
        <lang>-coding-style.md
        <lang>-testing.md
        <lang>-security.md
        <lang>-patterns.md
    settings.fragments/
        <hook-id>.json
    skills/                  (optional)
        <skill-name>/
            SKILL.md
```

Not every subdirectory is required — only create what you need. For a minimal addon, you need at minimum an agent, a hook, its fragment, and one or two rules.

---

## Step 1: Create the directories

```bash
mkdir -p addons/<lang>/agents
mkdir -p addons/<lang>/hooks
mkdir -p addons/<lang>/rules
mkdir -p addons/<lang>/settings.fragments
```

If any directory would otherwise be empty in the git repo, add a `.gitkeep`:

```bash
touch addons/<lang>/skills/.gitkeep
```

---

## Step 2: Write the specialist reviewer agent

Create `addons/<lang>/agents/<lang>-reviewer.md`. Model it on `addons/python/agents/python-reviewer.md`.

Required elements:

**Frontmatter:**

```yaml
---
name: python-reviewer
description: "Expert Python code reviewer. Use PROACTIVELY when reviewing Python code — FastAPI endpoints, async code, DataFrame pipelines, or any Python file. Use alongside the base code-reviewer for language-specific depth."
model: sonnet
color: yellow
tools: Read, Grep, Glob, Bash, Edit
memory: project
---
```

- `name` must be unique across all installed agents
- `description` is a routing signal — start with "Expert [lang] code reviewer. Use PROACTIVELY when..."
- `color` differentiates this agent visually from `code-reviewer` (which uses `cyan`)
- `tools` should include `Bash` for `git diff` and inline checks, but omit `Write` for read-only agents

**Opening block (read-only clause):**

```markdown
**You are a strictly read-only auditor. You MUST NOT modify any files, run chmod,
create files, or make any changes whatsoever — not even to /tmp.**
```

**Memory path discipline:**

```markdown
**Memory: If you write agent memory, always write it to the project root
`.claude/agent-memory/python-reviewer/` directory — never to a subdirectory's `.claude/`.**
```

**Review dimensions** — focus on the language's failure modes:
- Python: mutable defaults, async/sync boundaries, DataFrame join assertions, float-to-str casts
- TypeScript: unhandled promise rejections, `any` abuse, missing exhaustive checks
- Go: goroutine leaks, error wrapping, context propagation
- Rust: ownership violations, unsafe blocks, panic discipline

**Output format** — use the same structure as `code-reviewer.md` so the `/review` skill can consolidate findings:

```
## [Lang] Code Review Summary
**Files reviewed**: ...
**Risk level**: LOW | MEDIUM | HIGH

## Critical Issues (must fix)
## Improvements (should fix)
## Suggestions (nice to have)
## What's Done Well

## Review Summary
| Severity | Count | Status |
Verdict: APPROVE | WARNING | BLOCK — [reason]
```

---

## Step 3: Write the lint/format hook

Create `addons/<lang>/hooks/<lang>-check.sh`. Model it on `addons/python/hooks/ruff-check.sh`.

The hook pattern:

```bash
#!/bin/bash
# PostToolUse hook: run <linter> on edited <lang> files

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_response.filePath // empty')

# Only run on <lang> files
if [[ ! "$FILE_PATH" =~ \.<ext>$ ]]; then
  exit 0
fi

if [[ ! -f "$FILE_PATH" ]]; then
  exit 0
fi

PROJECT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"

# Path-flexible tool detection
TOOL=""
if [[ -x "$PROJECT_DIR/.venv/bin/<tool>" ]]; then
  TOOL="$PROJECT_DIR/.venv/bin/<tool>"
elif command -v <tool> >/dev/null 2>&1; then
  TOOL="<tool>"
fi

if [[ -z "$TOOL" ]]; then
  exit 0  # bail silently — tool not installed
fi

ERRORS=""
if ! OUTPUT=$($TOOL check "$FILE_PATH" 2>&1); then
  ERRORS="$OUTPUT"
fi

if [[ -n "$ERRORS" ]]; then
  jq -n --arg errors "$ERRORS" '{
    decision: "block",
    reason: ("<tool> found issues:\n" + $errors + "\nPlease fix these issues.")
  }'
fi
exit 0
```

From `addons/python/hooks/ruff-check.sh`, the ruff hook runs both `ruff check` (lint) and `ruff format --check` (format), accumulating errors from both before emitting the block decision.

**After writing the hook, set the executable bit:**

```bash
chmod +x addons/<lang>/hooks/<lang>-check.sh
```

The installer sets this automatically at install time, but you need it set in the repo for local testing.

---

## Step 4: Write the settings fragment

Create `addons/<lang>/settings.fragments/<hook-id>.json`. This wires the hook into Claude Code's `PostToolUse` event for Edit and Write tool calls.

Pattern from `addons/python/settings.fragments/ruff.json`:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/<lang>-check.sh",
            "statusMessage": "Running <linter>..."
          }
        ]
      }
    ]
  }
}
```

If your hook is `PreToolUse` (e.g. a safety hook like `mcp-postgres-safety`), change the event key accordingly.

---

## Step 5: Write the rules

Create 3-4 rules in `addons/<lang>/rules/`. Each covers one topic. Follow the naming pattern `<lang>-<topic>.md`.

Standard topics:

| File | Content |
|------|---------|
| `<lang>-coding-style.md` | Naming conventions, file organization, preferred idioms |
| `<lang>-testing.md` | Test framework, fixture patterns, parametrize, isolation |
| `<lang>-security.md` | Language-specific security pitfalls |
| `<lang>-patterns.md` | Idiomatic patterns the language community prefers |

From `addons/python/rules/python-coding-style.md`:

```markdown
# Python Coding Style

- Follow **PEP 8** conventions for naming and layout
- Use **type annotations** on all public function signatures
- Use **ruff** for linting and formatting
- `snake_case` for functions/variables, `PascalCase` for classes
- No mutable default arguments: `def f(x=[])` → `def f(x=None)`
- Use `pathlib.Path` for all file system operations, never `os.path.join`
- All resources (files, connections) must use `with` context managers
```

Keep rules concise and actionable. The rule will load in every conversation — every extra line has a cost.

---

## Step 6: Append to manifest.toml

Add one `[[artifacts]]` block per file. Append to the end of `manifest.toml`, before the `[presets]` section.

```toml
[[artifacts]]
id = "<lang>-reviewer"
type = "agent"
path = "addons/<lang>/agents/<lang>-reviewer.md"
description = "<Lang> specialist reviewer — [key areas]"
tags = ["<lang>", "review"]

[[artifacts]]
id = "<lang>-lint"
type = "hook"
path = "addons/<lang>/hooks/<lang>-check.sh"
settings_fragment = "addons/<lang>/settings.fragments/<hook-id>.json"
description = "PostToolUse <linter> check on edited <Lang> files"
tags = ["<lang>", "lint"]

[[artifacts]]
id = "<lang>-coding-style"
type = "rule"
path = "addons/<lang>/rules/<lang>-coding-style.md"
description = "<Lang>-specific coding style"
tags = ["<lang>", "style"]

[[artifacts]]
id = "<lang>-testing"
type = "rule"
path = "addons/<lang>/rules/<lang>-testing.md"
description = "<Lang> testing patterns"
tags = ["<lang>", "testing"]

[[artifacts]]
id = "<lang>-security"
type = "rule"
path = "addons/<lang>/rules/<lang>-security.md"
description = "<Lang> security pitfalls"
tags = ["<lang>", "security"]

[[artifacts]]
id = "<lang>-patterns"
type = "rule"
path = "addons/<lang>/rules/<lang>-patterns.md"
description = "<Lang> idiomatic patterns"
tags = ["<lang>", "patterns"]
```

Rules about choosing IDs:
- IDs are permanent after first release — `--uninstall` depends on them.
- Use the language name as a prefix so IDs don't collide across addons.
- Match the `id` to the filename (without extension) where possible.

---

## Step 7: Add the preset

Append the new preset to the `[presets]` section of `manifest.toml`:

```toml
<lang> = ["@preset:base-only", "<lang>-reviewer", "<lang>-lint", "<lang>-coding-style", "<lang>-testing", "<lang>-security", "<lang>-patterns"]
```

From the Python addon:

```toml
python = ["@preset:base-only", "python-reviewer", "ruff", "python-coding-style", "python-testing", "python-security", "python-patterns"]
```

If you want a combined preset (like `python-sql`), add it too:

```toml
<lang>-sql = ["@preset:<lang>", "@preset:sql"]
```

---

## Step 8: Lint + smoke test

**Lint the manifest:**

```bash
python3 -c "import tomllib; data = tomllib.load(open('manifest.toml','rb')); print('ok', len(data['artifacts']), 'artifacts')"
```

**Dry-run install:**

```bash
TMPDIR=$(mktemp -d)
./install.py --target "$TMPDIR" --preset <lang> --dry-run
```

Verify every expected artifact appears in the output.

**Real install into a temp directory:**

```bash
TMPDIR=$(mktemp -d)
./install.py --target "$TMPDIR" --preset <lang> --force
ls "$TMPDIR/.claude/agents/"
ls "$TMPDIR/.claude/hooks/"
ls "$TMPDIR/.claude/rules/"
```

Check that files landed in the right places and that `settings.json` contains the hook entry.

**Run the test suite:**

```bash
python3 -m pytest tests/ -v
# or: python3 -m unittest tests/test_install.py -v
```

All existing tests must still pass.

---

## Step 9: Update `base/rules/agents.md`

If the new addon ships a reviewer agent, add it to the "Available Agents" table in `base/rules/agents.md`:

```markdown
| <lang>-reviewer | <Lang> specialist review | Python/TypeScript/... code changes |
```

Include a note that it may not be present if the addon was not installed:

```markdown
> Language-specific reviewers (python-reviewer, typescript-reviewer, etc.) may be present
> if their addon is installed — use them alongside code-reviewer for language-specific depth.
```

This note already exists in `base/rules/agents.md`. You only need to add the row to the table.

---

## Step 10: Commit

One commit per addon:

```bash
git add addons/<lang>/
git add manifest.toml
git add base/rules/agents.md  # if updated
git commit -m "feat(addons/<lang>): add <lang> addon — reviewer, <linter> hook, rules"
```

Message format: `feat(addons/<lang>): ...` following the existing pattern (`feat(addons/python): ...`, `feat(addons/typescript): ...`).
