# Clank Template Repository — Design

**Status:** draft
**Date:** 2026-04-10
**Author:** Yasen Dimitrov (with Claude)

## Context

`clank` is a template repository for Claude Code customizations — sub-agents, skills, hooks, rules, and user-invokable skills (the current replacement for slash commands) — intended to be dropped into fresh projects via an installer script.

The user currently maintains a rich `.claude/` configuration inside `ice-scraper`, a production NHL data pipeline. That configuration has been refined over several months and encodes real lessons — destructive-SQL blocks, git-push reminders, a code-review agent with confidence-based filtering, a database integrity auditor, a pre-flight stop hook. This design lifts the reusable pieces into a language-agnostic template, adds per-language specialization, and wraps the whole thing in an installer script so the user can spin up a new project with a single command.

Two source materials shaped the design:

1. **`ice-scraper/.claude/`** — proven agents, hooks, and rules developed against a live production pipeline. The stripped-down versions of these artifacts are the backbone of `base/`.
2. **`affaan-m/everything-claude-code`** on GitHub — a multi-IDE configuration compendium whose per-language rule split (`common-<topic>` + `<language>-<topic>`) and specialist reviewer agent pattern directly influenced the addon structure and rule taxonomy used here.

## Goals

1. Provide a **language-agnostic baseline** (`base/`) that works in any project.
2. Ship **per-language addons** (`addons/<lang>/`) that specialize reviewers, hooks, and rules for Python, TypeScript/JavaScript, Go, Rust, and SQL (Postgres-first for the database side).
3. Install via a **fully configurable Python script** — presets for common cases, individual artifact selection, interactive conflict handling, and uninstall support.
4. Keep every artifact **reusable** — no hardcoded project paths, no assumptions about tool presence. Hooks bail gracefully if their tool isn't installed.
5. Mirror **ice-scraper's safety discipline** — destructive-SQL blocks, git-push reminders, stop-hook review nudges — without any ice-scraper-specific business context.

## Non-goals

- Not a Claude Code plugin in the marketplace sense (at least not v1). The install model is copy-into-target, not pluggable enable/disable.
- Not a multi-IDE compendium. Claude Code only.
- Does not ship application code, language runtimes, or build tooling.
- Does not manage the target project's `CLAUDE.md`. That file is the user's to own.
- Does not ship schema references, API docs, or any truly project-specific content — only scaffolds for places the user fills in (e.g. `querying-db/schema.txt.template`).

## Decisions locked in during brainstorming

- **Organization model: baseline + addons** (not one flat tree, not a menu). A Python-only project shouldn't copy a biome hook that never fires.
- **Install method: Python script** (not manual copy-paste, not a Claude Code plugin).
- **Languages at launch: Python, TypeScript/JavaScript, Go, Rust, SQL** (five addons).
- **Installer philosophy: everything configurable.** Every agent, hook, skill, and rule has a stable ID; users can select presets, individual IDs, or both.
- **Conflict handling: interactive prompt per file** (`skip`/`overwrite`/`diff`/`abort`), with `--force` to bypass.
- **Install receipt + uninstall both in v1.**
- **Stop-review-reminder hook is opt-in** — installer prompts before enabling it.
- **Commands are out.** User-invokable entry points ship as skills with `disable-model-invocation: true`, matching how ice-scraper does it.
- **`refactor-cleaner` agent is dropped** — the `code-simplifier` plugin covers that need.
- **Tests + CI are in.** The installer is the one piece of actual code and deserves regression guards.

---

## Architecture

### Directory layout

```
clank/
├── README.md
├── CLAUDE.md                   # authoring philosophy, expanded from current
├── install.py                  # the installer — Python 3.11+, stdlib only
├── manifest.toml               # source of truth for artifacts + presets
├── base/
│   ├── agents/
│   ├── hooks/
│   ├── rules/
│   ├── skills/
│   ├── plugins/                # reference docs; NOT auto-loaded by Claude Code
│   ├── settings.json           # reference wiring — only the base-tagged hooks
│   └── settings.fragments/     # per-hook JSON fragments the installer merges
├── addons/
│   ├── python/
│   │   ├── agents/
│   │   ├── hooks/
│   │   ├── rules/
│   │   ├── skills/
│   │   └── settings.fragments/
│   ├── typescript/
│   ├── go/
│   ├── rust/
│   └── sql/
├── docs/
│   ├── install.md
│   ├── authoring-agents.md
│   ├── authoring-hooks.md
│   ├── authoring-skills.md
│   ├── authoring-rules.md
│   └── adding-an-addon.md
├── tests/
│   └── test_install.py         # stdlib unittest, no pytest dependency
└── .github/workflows/test.yml
```

### Mapping to target

`base/` and `addons/<lang>/` are **virtual `.claude/` trees**. At install time, everything under them is copied into `<target>/.claude/` — never the target repo root, never `<target>/CLAUDE.md`.

Example:

| Source in clank | Destination in target |
|-----------------|-----------------------|
| `base/agents/code-reviewer.md` | `<target>/.claude/agents/code-reviewer.md` |
| `base/hooks/pretooluse-bash-safety.sh` | `<target>/.claude/hooks/pretooluse-bash-safety.sh` |
| `base/rules/coding-style.md` | `<target>/.claude/rules/coding-style.md` |
| `base/plugins/plugins.md` | `<target>/.claude/plugins/plugins.md` |
| `addons/python/hooks/ruff-check.sh` | `<target>/.claude/hooks/ruff-check.sh` |
| `addons/sql/skills/querying-db/SKILL.md` | `<target>/.claude/skills/querying-db/SKILL.md` |

`.claude/plugins/` is **not** a standard Claude Code auto-load location, so `plugins/plugins.md` is a reference file the user can browse, not context that ships with every prompt. That matches the user's intent ("a file to note plugins I'd like to install").

### Key design decisions

**Manifest as source of truth.** Artifacts are identified by stable string IDs declared in `manifest.toml`, not inferred from filesystem paths. This lets presets reference IDs, makes `--list` trivial, enables `--uninstall` via an install receipt, and prevents "I renamed the file but nothing points to it anymore" drift.

**Per-hook settings fragments.** Each hook ships its own `settings.fragments/<hook-id>.json` instead of a monolithic per-addon fragment. The installer composes exactly the fragments for selected hooks, allowing fine-grained selection like `--include bash-safety --exclude file-safety`. More files in the repo, but the installer stays precise.

**Target writes go only under `<target>/.claude/`.** Hard rule. Enforced by the installer path check and backed by a test scenario.

**TOML, not YAML, for the manifest.** Python stdlib has `tomllib` (3.11+) but not a YAML parser. Using TOML keeps the installer dependency-free. Human-readability is roughly equivalent for this use case.

**Python 3.11+ required.** For `tomllib`. Documented in `docs/install.md`.

---

## `manifest.toml`

Schema:

```toml
version = 1

[[artifacts]]
id = "code-reviewer"
type = "agent"                          # agent | hook | rule | skill | plugin-doc
path = "base/agents/code-reviewer.md"   # file path for agent/hook/rule/plugin-doc; directory path for skill
description = "Language-agnostic code reviewer"
tags = ["base", "review"]

[[artifacts]]
id = "bash-safety"
type = "hook"
path = "base/hooks/pretooluse-bash-safety.sh"
settings_fragment = "base/settings.fragments/bash-safety.json"
description = "PreToolUse Bash guardrails — destructive SQL, rm, git push reminder"
tags = ["base", "safety"]

[[artifacts]]
id = "stop-review-reminder"
type = "hook"
path = "base/hooks/stop-review-reminder.sh"
settings_fragment = "base/settings.fragments/stop-review-reminder.json"
description = "Stop hook that nudges to run code-reviewer on code changes"
tags = ["base", "review"]
default = false                         # excluded from @tag/@preset expansion; installer prompts once

[[artifacts]]
id = "database-reviewer"
type = "agent"
path = "base/agents/database-reviewer.md"
description = "Postgres database integrity auditor"
tags = ["base", "review", "postgres"]
requires_mcp = ["postgres"]             # soft hint surfaced in install summary

[[artifacts]]
id = "review"
type = "skill"
path = "base/skills/review"             # directory — installer copies recursively
description = "User-invokable /review skill that runs code-reviewer on recent changes"
tags = ["base", "review"]

[[artifacts]]
id = "plugins-doc"
type = "plugin-doc"
path = "base/plugins/plugins.md"
description = "Reference list of Claude Code plugins the user typically installs"
tags = ["base", "docs"]

# … every other artifact …

[[artifacts]]
id = "ruff"
type = "hook"
path = "addons/python/hooks/ruff-check.sh"
settings_fragment = "addons/python/settings.fragments/ruff.json"
description = "PostToolUse ruff check on edited Python files"
tags = ["python", "lint"]

[presets]
minimal = ["bash-safety", "file-safety", "code-reviewer", "executing-actions-with-care"]
base-only = ["@tag:base"]
python = ["@preset:base-only", "python-reviewer", "ruff", "python-coding-style", "python-testing", "python-security", "python-patterns"]
typescript = ["@preset:base-only", "typescript-reviewer", "biome", "svelte-check", "typescript-coding-style", "typescript-testing", "typescript-security", "typescript-patterns"]
go = ["@preset:base-only", "go-reviewer", "golangci-lint", "golang-coding-style", "golang-testing", "golang-security", "golang-patterns"]
rust = ["@preset:base-only", "rust-reviewer", "cargo-clippy", "rust-coding-style", "rust-testing", "rust-security"]
sql = ["@preset:base-only", "sql-reviewer", "mcp-postgres-safety", "sql-safety", "querying-db", "migration"]
python-sql = ["@preset:python", "@preset:sql"]
typescript-sql = ["@preset:typescript", "@preset:sql"]
fullstack-python = ["@preset:python", "@preset:typescript", "@preset:sql"]
all = ["@tag:*"]
```

### Special directives in preset lists

- `@tag:<name>` — expands to every artifact with that tag
- `@tag:*` — every artifact
- `@preset:<name>` — expands to that preset's members (recursively flattened)

The installer resolves directives into a flat ID set, then applies `--include` (union) and `--exclude` (difference) on top.

### Validation

A manifest lint step runs on every install and in CI:

- Every `path` exists on disk.
- Every `settings_fragment` exists and parses as JSON.
- No duplicate `id` values.
- Every preset member resolves to a known ID or a valid directive.
- Every `@preset:` reference targets a preset that exists.
- No circular preset references.

---

## Installer: `install.py`

### CLI

```
./install.py --target <path> [selection] [options]
```

**Selection (at least one required):**

- `--preset <name>` — named bundle from `manifest.toml`
- `--include <id1,id2,…>` — explicit artifact IDs, composable with `--preset`
- `--exclude <id1,id2,…>` — remove from current selection
- `--interactive` / `-i` — numbered-list picker grouped by category (agents / hooks / rules / skills / plugin-docs / addons). Implementation: stdlib `input()` loop; each category prints a numbered list with `[x]`/`[ ]` checkboxes, user types numbers to toggle, `a` for all, `n` for none, `c` to continue to next category. No `curses`/`termios` dependency — portable across terminals and CI.

**Other options:**

- `--dry-run` — print what would be copied, write nothing
- `--force` — overwrite existing files, no per-file prompts
- `--list` — print manifest (every ID + description + tags) and exit
- `--uninstall <ids>` — remove listed artifacts, reverse-merge their settings fragments
- `--version` — print clank version and exit

### Install sequence

1. **Parse args and load manifest.** Validate the manifest (lint step above). Abort on any failure.
2. **Resolve selection.** Expand preset(s) → directives → IDs. Apply `--include`/`--exclude`. Warn on unknown IDs.
3. **Safety checks.**
   - `<target>` must exist and be a directory.
   - `<target>` must not be clank itself (detected by `manifest.toml` at its root).
   - `<target>/.claude/` is created if missing.
4. **Stop-hook prompt.** Artifacts with `default = false` in the manifest are excluded from `@tag:*` and `@preset:*` expansion; they only enter the selection via explicit `--include <id>`. For `stop-review-reminder` specifically, the installer always asks once during a normal install: "Include the stop hook that reminds you to run code-reviewer on code changes? [y/N]". The prompt fires even if the user didn't mention it — it's a deliberate one-time opt-in. `--force` skips the prompt and defaults to "no" unless `--include stop-review-reminder` was explicitly passed. `--dry-run` prints the question but defaults to "no" without prompting.
5. **Copy files.** For each selected artifact:
   - Compute destination by stripping the `base/` or `addons/<name>/` prefix and prepending `<target>/.claude/`.
   - If `type = "skill"`, the source path is a directory — copy it recursively (every file under it lands at the mirrored destination). Conflict handling applies per-file.
   - Otherwise the source path is a single file — copy it, applying conflict handling if the destination exists.
   - For hooks (`type = "hook"`), preserve the executable bit via explicit `chmod +x` after copy.
6. **Merge settings fragments.** For each selected hook with a fragment:
   - If `<target>/.claude/settings.json` doesn't exist, seed from `base/settings.json`.
   - Deep-merge the fragment (algorithm below).
7. **Write install receipt** to `<target>/.claude/.clank-installed.json`:
   ```json
   {
     "clank_version": "0.1.0",
     "clank_commit": "<git sha>",
     "installed_at": "2026-04-10T12:34:56Z",
     "target": "/path/to/project",
     "artifacts": ["code-reviewer", "bash-safety", "python-reviewer", "ruff", …]
   }
   ```
8. **Print summary.**
   - What was added (by category)
   - What was skipped (by user or by default=false)
   - Next steps ("review `.claude/plugins/plugins.md` and install recommended plugins", "edit `.claude/skills/deploy/SKILL.md` to add your deploy command", etc.)
   - Soft warnings for `requires_mcp` hints ("`database-reviewer` expects a `postgres` MCP server")

### Conflict handling

Default (no `--force`): for each file that already exists at the destination, prompt:

```
Conflict: .claude/agents/code-reviewer.md already exists.
[s]kip / [o]verwrite / [d]iff / [a]bort >
```

- `skip` — leave target unchanged, don't add this ID to the receipt
- `overwrite` — replace the file
- `diff` — print `diff` output and re-prompt
- `abort` — stop the install (files already copied are **not** rolled back; a partial receipt is still written so `--uninstall` can undo)

`--force` overrides every conflict to `overwrite`. `--dry-run` lists conflicts with no prompting.

### Settings.json deep merge

The target's `settings.json` is treated as the source of truth; clank additively merges on top.

- **`hooks.<event>[]`**: iterate fragment entries. For each, check if the target has an entry with the same `matcher`:
  - Match → append fragment's `hooks[]` items to target's, deduped by `command` string
  - No match → append the whole fragment entry
- **`permissions.allow[]`**: set-union (dedupe on exact string)
- **`permissions.deny[]`**: set-union
- **`enabledPlugins`**: target wins on key conflicts unless `--force`
- **Other scalar/object keys**: target wins on conflict unless `--force`

Re-running the installer is idempotent — dedupe by `command` means the same hook entry isn't added twice.

### Uninstall

`--uninstall <id1,id2,…>` reads the install receipt and, for each ID:

1. Removes the file at the computed destination path.
2. If the ID had a `settings_fragment`, locates the corresponding entries in `<target>/.claude/settings.json` and removes them:
   - Removes the specific `command` entries from matching `matcher` groups.
   - If a `matcher` group ends up empty, removes the whole group.
   - Removes the matching `permissions.allow[]` entries.
3. Updates the receipt to drop the uninstalled IDs.
4. If the receipt is now empty, prints a note suggesting the user also delete empty directories (installer doesn't auto-delete dirs — too easy to lose unrelated files).

### Safety guarantees

- Never writes outside `<target>/.claude/` except the receipt file (which lives inside `.claude/`).
- Never modifies `<target>/CLAUDE.md` or any file at the target repo root.
- Never deletes files not listed in the install receipt.
- Refuses to run if `--target` is clank itself.
- Refuses to run if `--target` doesn't exist.
- Bails before any writes if the manifest fails linting.

---

## `base/` contents

### `base/agents/`

| ID | File | Origin | Purpose |
|----|------|--------|---------|
| `code-reviewer` | `agents/code-reviewer.md` | Lifted from ice-scraper's `code-reviewer.md`, stripped | Language-agnostic reviewer. Keeps: confidence-based filtering, review dimensions (correctness, security, error handling, simplicity, performance, AI-code quirks), severity mapping, output format, approval criteria, behavioral guidelines, shell safety note. Drops: Database Schema Validation, Python Best Practices, FastAPI Patterns, DataFrame specifics, Project Style & Conventions — these move to addons. |
| `security-reviewer` | `agents/security-reviewer.md` | New | Narrow OWASP Top 10 focus: injection (SQL/command/XSS), hardcoded secrets, eval/exec, unsafe deserialization, weak crypto, path traversal, auth/authz bypass, secrets in logs. Read-only. |
| `database-reviewer` | `agents/database-reviewer.md` | Lifted from ice-scraper's `db-integrity-auditor.md`, stripped | Postgres database integrity auditor. Keeps Phases 1-6: schema validation, data completeness, uniqueness, referential integrity, accuracy/format, operational health. Drops ice-scraper "Critical Project Context" and "Known Gotchas" (game_id float casts, signal lifecycle, odds opening/closing, MoneyPuck quirks). Works against any Postgres database via the `postgres` MCP. Read-only. |
| `docs-researcher` | `agents/docs-researcher.md` | New | Dedicated agent for fetching up-to-date library/framework docs. Uses `ctx7` CLI per the user's global rule, falls back to WebFetch. Protects main context window from large doc dumps. |
| `doc-updater` | `agents/doc-updater.md` | New | Reviews recently modified code against existing docs (README, API references, in-repo guides) and reports stale sections that need updating. Does not write. |

### `base/hooks/`

| ID | File | Origin | Notes |
|----|------|--------|-------|
| `bash-safety` | `hooks/pretooluse-bash-safety.sh` | Lifted from `pretooluse-bash-checks.sh`, stripped | Keeps: git-push reminder, destructive SQL block (DROP/TRUNCATE/DELETE FROM), UPDATE block, `rm` block, tmux long-running reminder. Drops: biome `--unsafe`, pip-vs-uv, scp-to-VPS, ice-scraper model/backtest script names. |
| `file-safety` | `hooks/pretooluse-file-safety.sh` | Generalized from `pretooluse-file-checks.sh` | Blocks writes that introduce destructive DDL in files matching configurable patterns. The patterns + forbidden content regexes are declared in a config block at the top of the script (default: `*schema*`, `*.sql`, `migrations/*` → block `DROP TABLE`, `DROP COLUMN`, `TRUNCATE`, unbounded `DELETE`). Users can edit the config block after install. |
| `stop-review-reminder` | `hooks/stop-review-reminder.sh` | Lifted from `stop-checks.sh`, parameterized | Same marker-file + git-diff approach. File-extension filter is a variable at top of the script (default: `.py .ts .tsx .js .jsx .go .rs .svelte .sh .sql`). Reminder text: "run code-reviewer, consider `/simplify` if available." `default = false` in manifest — installer prompts. |

Language-specific linting hooks (`ruff`, `biome`, `svelte-check`, `golangci-lint`, `cargo-clippy`, `mcp-postgres-safety`) live in their respective addons.

### `base/rules/`

| ID | File | Origin | Notes |
|----|------|--------|-------|
| `code-review` | `rules/code-review.md` | Lifted from ice-scraper, small generalizations | Drops the DataFrame-specific bullet. |
| `long-running-scripts` | `rules/long-running-scripts.md` | Lifted verbatim | Already 100% generic. |
| `no-inline-comments` | `rules/no-inline-comments.md` | Lifted verbatim | `python -c` + bash pitfall is universal; belongs in base per user decision. |
| `update-agent-memory` | `rules/update-agent-memory.md` | Lifted, example generalized | Drops the `db-integrity-auditor` mention. |
| `use-project-code-reviewer` | `rules/use-project-code-reviewer.md` | Lifted, generalized | Generic version: prefer the project's `code-reviewer` agent over superpowers'. |
| `executing-actions-with-care` | `rules/executing-actions-with-care.md` | New | Distills reversibility / blast-radius doctrine from the Claude Code system-prompt default into an explicit project rule. |
| `agents` | `rules/agents.md` | New, modeled on affaan-m's `common/agents.md` | **Index of clank's agents** with "when to use" table and parallel-execution guidance. Lists: code-reviewer, security-reviewer, database-reviewer, docs-researcher, doc-updater, plus whichever language reviewers are installed. |
| `testing` | `rules/testing.md` | Lifted from affaan-m's `common/testing.md` | TDD workflow (RED → GREEN → REFACTOR), AAA test structure, descriptive test naming. Light edits to drop the `tdd-guide` agent reference (we don't ship that). |
| `coding-style` | `rules/coding-style.md` | Lifted from affaan-m's `common/coding-style.md` | KISS/DRY/YAGNI, file organization (<800 lines), naming conventions, immutability principle, code quality checklist. |

### `base/skills/`

Skill manifest paths point to the **skill directory**, not the `SKILL.md` file. The installer copies skill directories recursively so supporting files (examples, scaffolds, schema templates) ship alongside `SKILL.md` without needing a separate artifact entry. For single-file skills this is a no-op.

All user-invokable skills use `disable-model-invocation: true` in frontmatter so they activate only when the user types `/<skill-name>` — matching ice-scraper's pattern for `migration` and `deploy`.

| ID | Path | Invocation | Purpose |
|----|------|------------|---------|
| `review` | `base/skills/review/` | `/review` | Runs `code-reviewer` agent on recent changes. Runs `security-reviewer` in parallel if the changes touch auth/crypto/input-validation code. |
| `smoke-test` | `base/skills/smoke-test/` | `/smoke-test` | Walks through the `long-running-scripts.md` checklist before executing an expensive script (imports, DB connection, dependencies, memory). |
| `deploy` | `base/skills/deploy/` | `/deploy` | **Scaffold**, not a working skill. Ships generic workflow (pre-flight → deploy → verify → rollback) with `# TODO: fill in your deploy command` placeholders. User edits after install. |

### `base/plugins/`

| File | Content |
|------|---------|
| `plugins.md` | Reference doc listing plugins the user typically wants installed. Distilled from affaan-m's `plugins/README.md`: `superpowers`, `code-simplifier`, `pyright-lsp`, `typescript-lsp`, postgres MCP server, `context7`, `hookify`. Includes the `claude plugin marketplace add` + `claude plugin install` commands. NOT auto-loaded by Claude Code — this is a reference file the user browses. |

### `base/settings.json`

Reference wiring that only uses base-tagged hooks. Drives what the installer seeds into a target that doesn't yet have a `settings.json`.

```json
{
  "permissions": { "allow": [] },
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [{ "type": "command", "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/pretooluse-bash-safety.sh", "statusMessage": "Bash safety checks..." }]
      },
      {
        "matcher": "Edit|Write",
        "hooks": [{ "type": "command", "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/pretooluse-file-safety.sh", "statusMessage": "File safety checks..." }]
      }
    ]
  }
}
```

`stop-review-reminder` is added only if the user accepted the prompt. Addon hooks are added via fragment merge.

### `base/settings.fragments/`

One small JSON file per hook:

- `bash-safety.json` — PreToolUse Bash hook entry
- `file-safety.json` — PreToolUse Edit|Write hook entry
- `stop-review-reminder.json` — Stop hook entry

---

## Addon contents

Each addon mirrors the base layout:

```
addons/<name>/
├── agents/
├── hooks/
├── rules/
├── skills/
└── settings.fragments/
```

### `addons/python/`

| ID | File | Origin |
|----|------|--------|
| `python-reviewer` | `agents/python-reviewer.md` | Lifted from ice-scraper's `code-reviewer.md` — **keeps** Python Best Practices, FastAPI Patterns, DataFrame integrity checks that were stripped from base. Deep Python specialist. |
| `ruff` | `hooks/ruff-check.sh` | Lifted from ice-scraper, path-flexible. Search order: `./venv/bin/ruff` → `./.venv/bin/ruff` → `uv run ruff` → `ruff` on `PATH`. Bails silently if not found. |
| `python-coding-style` | `rules/python-coding-style.md` | Lifted from affaan-m |
| `python-testing` | `rules/python-testing.md` | Lifted from affaan-m |
| `python-security` | `rules/python-security.md` | Lifted from affaan-m |
| `python-patterns` | `rules/python-patterns.md` | Lifted from affaan-m |

Fragment: `settings.fragments/ruff.json` adds `ruff-check.sh` to `PostToolUse[Edit|Write]`.

### `addons/typescript/`

Covers TS and JS — biome handles both. Svelte-check is included here (not a separate addon) because the hook is inert on non-Svelte files; a note in the hook explains this.

| ID | File | Origin |
|----|------|--------|
| `typescript-reviewer` | `agents/typescript-reviewer.md` | New. TS/JS specialist: strict types, no `any`, React hooks rules, promise handling, import/export hygiene, Next.js server-component caveats. |
| `biome` | `hooks/biome-check.sh` | Lifted, de-hardcoded. Search order: `./node_modules/.bin/biome` → `./frontend/node_modules/.bin/biome` → `biome` on `PATH`. Drops ice-scraper's `frontend/src/` path filter. |
| `svelte-check` | `hooks/svelte-check.sh` | Lifted, made optional. Only fires on `*.svelte` files. Bails silently if `svelte-check` isn't installed. Header note: "included in the typescript addon because Svelte is a TS project with extra steps; safe to leave installed on non-Svelte projects." |
| `typescript-coding-style` | `rules/typescript-coding-style.md` | Lifted from affaan-m |
| `typescript-testing` | `rules/typescript-testing.md` | Lifted from affaan-m |
| `typescript-security` | `rules/typescript-security.md` | Lifted from affaan-m |
| `typescript-patterns` | `rules/typescript-patterns.md` | Lifted from affaan-m |

Fragments: `biome.json`, `svelte-check.json` — both add to `PostToolUse`.

### `addons/go/`

| ID | File | Origin |
|----|------|--------|
| `go-reviewer` | `agents/go-reviewer.md` | New. Go specialist: error wrapping (`fmt.Errorf` with `%w`), `context.Context` propagation, goroutine leak patterns, channel direction, `sync.Mutex` vs `sync.RWMutex`, nil pointer checks, proper `defer` placement. |
| `golangci-lint` | `hooks/golangci-lint-check.sh` | New. Runs `golangci-lint run` on the package directory of an edited `.go` file. Bails silently if not installed or not a Go module. |
| `golang-coding-style` | `rules/golang-coding-style.md` | Lifted from affaan-m |
| `golang-testing` | `rules/golang-testing.md` | Lifted from affaan-m |
| `golang-security` | `rules/golang-security.md` | Lifted from affaan-m |
| `golang-patterns` | `rules/golang-patterns.md` | Lifted from affaan-m |

Fragment: `golangci-lint.json`.

### `addons/rust/`

Affaan-m has no Rust rules; these are written fresh, short and to the point.

| ID | File | Origin |
|----|------|--------|
| `rust-reviewer` | `agents/rust-reviewer.md` | New. Rust specialist: ownership/borrow hints, lifetimes, `unsafe` scrutiny, `Result`/`Option` discipline, common clippy lints, `async`/`tokio` idioms, `?` operator usage. |
| `cargo-clippy` | `hooks/cargo-clippy-check.sh` | New. Runs `cargo clippy --workspace --all-targets -- -D warnings` on edits inside a Cargo workspace. Bails silently if not a Cargo project. |
| `rust-coding-style` | `rules/rust-coding-style.md` | New |
| `rust-testing` | `rules/rust-testing.md` | New |
| `rust-security` | `rules/rust-security.md` | New |

Fragment: `cargo-clippy.json`.

### `addons/sql/`

Not a language per se — it's "SQL + a relational database (Postgres-first, since that's what the MCP targets)". Follows the same structure for install consistency.

| ID | File | Origin |
|----|------|--------|
| `sql-reviewer` | `agents/sql-reviewer.md` | New. Distinct from base `database-reviewer` (which audits database **health**). This one reviews **queries** for: parameterization (SQL injection), N+1 patterns, missing indexes, EXPLAIN-worthy cost, window/CTE clarity, use of `SELECT *`. |
| `mcp-postgres-safety` | `hooks/pretooluse-mcp-postgres-safety.sh` | Lifted from `pretooluse-mcp-postgres-checks.sh` — already ~95% generic. Drops the `/tmp/<name>.py` ice-scraper idiom from the error message. Blocks DROP/TRUNCATE/DELETE/UPDATE through the `mcp__postgres__query` tool; warns on ALTER/INSERT. |
| `sql-safety` | `rules/sql-safety.md` | New. Destructive DDL rules, migration safety, parameterized-query discipline, schema change approval. |
| `querying-db` | `addons/sql/skills/querying-db/` | Lifted from ice-scraper's `querying-db` skill, generalized. Skill directory contains `SKILL.md` + `schema.txt.template` (scaffold for the user's schema reference — user renames to `schema.txt` and fills in). Workflow: "read `<project>/.claude/skills/querying-db/schema.txt` first" → "use `mcp__postgres__query`" → "fallback via project's DB connection helper". Ships without a real `schema.txt`. |
| `migration` | `addons/sql/skills/migration/` | Lifted from ice-scraper's `migration` skill, generalized. **Scaffold**. Keeps: idempotency principles (`IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`), no-destructive-DDL rule, step-by-step workflow shape. Drops ice-scraper's `MIGRATIONS` list + `schema.py` specifics. Includes a "your migration system" section the user edits to describe their toolchain (Alembic, Django migrations, raw SQL files, `golang-migrate`, etc.). |

Fragment: `mcp-postgres-safety.json` adds the hook to `PreToolUse[mcp__postgres__query]`.

---

## Docs (`docs/` in clank itself — not copied to target)

| File | Content |
|------|---------|
| `install.md` | Complete installer CLI reference: every flag, example invocations, conflict behavior, receipt format, uninstall workflow, Python 3.11+ requirement. |
| `authoring-agents.md` | How to add a new agent: frontmatter fields (`name`, `description`, `tools`, `model`, `memory`), read-only agent conventions, memory path discipline, writing `description` as a router signal (not human docs). |
| `authoring-hooks.md` | Hook lifecycle, exit code semantics (0 pass / 1 warn / 2 block / JSON stdin-stdout pattern), path-flexible tool detection pattern, testing hooks with `echo '{...}' \| ./hook.sh`. |
| `authoring-skills.md` | Skill frontmatter, the `disable-model-invocation: true` pattern for `/invocations`, supporting files, how skills differ from the (deprecated) commands directory. |
| `authoring-rules.md` | What makes a good rule fragment, why they auto-load as project instructions, when NOT to use them (e.g. for large reference docs that would bloat every prompt). |
| `adding-an-addon.md` | Step-by-step walkthrough of adding a new language addon — uses `addons/python/` as the worked example. Covers manifest entries, fragment files, and updating the agents index rule. |

## Repo root files

### `README.md` (full rewrite)

Replaces the current one-liner. Structure:

1. **What clank is** — one-paragraph pitch
2. **Quickstart** — `git clone`, `./install.py --target <path> --preset python-sql`
3. **Presets** — table from manifest
4. **Individual artifacts** — pointer to `./install.py --list`
5. **Conflict handling** — short summary + link to `docs/install.md`
6. **Uninstall** — one sentence + example
7. **Extending clank** — link to `docs/adding-an-addon.md`
8. **Credits / inspired by** — ice-scraper internals, affaan-m's everything-claude-code

### `CLAUDE.md` (expanded)

Keep the current authoring philosophy. Add:

- Pointer to `docs/` for the concrete how-tos
- Note that clank's own `.claude/` is empty — the template lives in `base/` + `addons/` and isn't active while editing clank
- Hard rules:
  - Artifacts must not hardcode absolute paths or absolute repo paths
  - Hooks must bail gracefully (exit 0) if their required tool isn't installed
  - Agents declared read-only must not use Bash for write operations
  - Every new artifact goes in `manifest.toml` or it doesn't ship
  - Every `settings_fragment` must be independently valid JSON
- Link to ice-scraper and affaan-m/everything-claude-code as source material

### `.gitignore`

Python (`__pycache__/`, `*.pyc`), test scratch (`tests/tmp/`, `tests/.clank-test-*/`), editor noise (`.vscode/`, `.idea/`, `*.swp`).

---

## Tests

### `tests/test_install.py`

stdlib `unittest`, no pytest dependency.

**Scenario 1: Clean install into empty target**
- Create an empty tmp directory.
- Run `install.py --target <tmp> --preset python`.
- Assert every Python + base artifact file exists at its expected path.
- Assert `<tmp>/.claude/settings.json` exists, has the bash-safety + file-safety + ruff entries under the right matchers.
- Assert hooks are executable.
- Assert `.clank-installed.json` receipt exists and lists the selected IDs.

**Scenario 2: Install over existing `.claude/` with unrelated hooks**
- Seed `<tmp>/.claude/settings.json` with pre-existing entries: an unrelated `PreToolUse[Read]` hook, a populated `permissions.allow[]` list, an `enabledPlugins` dict.
- Run `install.py --target <tmp> --preset typescript --force`.
- Assert unrelated hook entries preserved.
- Assert existing `permissions.allow[]` entries preserved (set-union with anything we add).
- Assert `enabledPlugins` untouched.
- Assert new biome entries added exactly once (not duplicated into the existing `PreToolUse` block).
- Re-run the same install. Assert still idempotent — no duplicate `command` strings in any hook group.

**Scenario 3: Uninstall round-trip**
- Install `--preset sql` into an empty target.
- Run `--uninstall querying-db,migration`.
- Assert those two files are gone, the remaining SQL artifacts are still there.
- Assert the receipt is updated (those two IDs dropped).
- Run `--uninstall <remaining sql IDs>`. Assert `settings.json` no longer has the mcp-postgres-safety entry, but the base hooks are still wired.

**Scenario 4: Manifest lint**
- Load and validate `manifest.toml` using the installer's validation function.
- Assert no errors on the shipped manifest.
- Temporarily mutate a path to point at a nonexistent file → assert the lint function catches it.
- Temporarily add a duplicate ID → assert lint catches it.
- Temporarily add a preset referencing a nonexistent ID → assert lint catches it.

### `.github/workflows/test.yml`

```yaml
name: test
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: python -m unittest tests/test_install.py -v
```

---

## Open decisions / explicit non-decisions

- **Skills in `base/` are minimal by design.** `review`, `smoke-test`, and `deploy` (scaffold) only. More skills can ship in addons or be added later. The user noted they already plan to install the `code-simplifier` plugin, which covers `/simplify`.
- **`addons/svelte/` is not a separate addon.** Svelte-check lives inside `addons/typescript/`. This may change if the typescript addon gets too big or if a user with strong non-Svelte preferences objects.
- **Version field in manifest is `1`.** Reserved for future schema migration; installer treats anything other than `1` as an error until a migration path is defined.
- **The receipt format is not versioned yet.** Adding a `format_version: 1` field later is a safe additive change.
- **Target Claude Code version is not pinned.** Artifacts assume current Claude Code conventions as of April 2026. If conventions shift (e.g. `.claude/plugins/` becomes auto-loaded), clank artifacts will need a corresponding update.
- **The installer does not attempt to install Claude Code plugins** listed in `plugins.md`. That file is a checklist for the user, not an automation target.

## Work breakdown for implementation

In rough dependency order:

1. Create `manifest.toml` with the full artifact list (ids + paths + descriptions + tags), even before the files exist.
2. Write `install.py` (stdlib only) with: arg parsing, manifest loading, manifest lint, selection resolution (presets/tags/directives), safety checks, copy logic, settings merge, receipt write, uninstall, conflict prompting, interactive mode.
3. Write `tests/test_install.py` against the installer + a fixture manifest.
4. Add `.github/workflows/test.yml`.
5. Write `base/` artifacts:
   - agents (code-reviewer, security-reviewer, database-reviewer, docs-researcher, doc-updater)
   - hooks (bash-safety, file-safety, stop-review-reminder) + fragments
   - rules (code-review, long-running-scripts, no-inline-comments, update-agent-memory, use-project-code-reviewer, executing-actions-with-care, agents, testing, coding-style)
   - skills (review, smoke-test, deploy scaffold)
   - plugins/plugins.md
   - settings.json reference wiring
6. Write `addons/python/` artifacts.
7. Write `addons/typescript/` artifacts.
8. Write `addons/sql/` artifacts.
9. Write `addons/go/` artifacts.
10. Write `addons/rust/` artifacts.
11. Write `docs/` files.
12. Rewrite `README.md` and expand `CLAUDE.md`.
13. Run the installer end-to-end against a throwaway target directory, verify everything works, iterate on any friction.

Detailed implementation planning is handled by the writing-plans skill in the next phase.
