# clank

A template repository of Claude Code customizations — agents, hooks, rules, skills — that you install into new projects with a single command.

## What clank is

clank packages the Claude Code configuration patterns that actually work in production: code-review agents with confidence filtering, PreToolUse safety hooks that block destructive SQL and accidental `rm`, per-language specialist reviewers, and rules that encode hard-won process lessons. Instead of copy-pasting from a prior project every time, you run the installer, pick a preset, and get a fully wired `.claude/` directory in seconds. Everything is configurable — select individual artifacts, exclude what you don't need, or use the interactive picker to browse all 50 artifacts before installing.

## Quickstart

```bash
git clone git@github.com:blancpain/clank.git
cd clank
./install.py --target ~/repos/new-project --preset python-sql
```

That copies every artifact for Python + SQL into `~/repos/new-project/.claude/`, merges hook entries into `settings.json`, and writes a receipt at `~/repos/new-project/.claude/.clank-installed.json`.

See [docs/install.md](docs/install.md) for the full flag reference.

## Requirements

- **Python 3.11+** — the installer uses `tomllib` from the standard library. No third-party packages.
- **git** — used to record the clank commit in the install receipt. Optional; install proceeds with commit logged as `unknown` if not found.
- **bash** — all hook scripts are `/bin/bash` scripts.
- **jq** — required by the base safety hooks (`bash-safety`, `file-safety`, `stop-review-reminder`).

**Optional per-addon tools (auto-detected; hooks bail silently if absent):**

| Tool | Used by |
|------|---------|
| `ruff` | Python `ruff` lint hook |
| `biome` | TypeScript `biome` lint hook |
| `svelte-check` | TypeScript `svelte-check` lint hook |
| `golangci-lint` | Go `golangci-lint` lint hook |
| `cargo` / `clippy` | Rust `cargo-clippy` lint hook |

## Presets

Pass `--preset <name>` to install a named bundle. Presets are composable — each language preset includes `base-only` automatically.

| Preset | What it installs |
|--------|-----------------|
| `minimal` | Core safety hooks + code-reviewer agent + actions-with-care rule |
| `base-only` | All language-agnostic artifacts: 5 agents, 2 safety hooks, 8 rules, 3 skills, plugin doc |
| `python` | base-only + Python reviewer, ruff hook, Python coding/testing/security/patterns rules |
| `typescript` | base-only + TypeScript reviewer, biome, svelte-check, TypeScript coding/testing/security/patterns rules |
| `go` | base-only + Go reviewer, golangci-lint, Go coding/testing/security/patterns rules |
| `rust` | base-only + Rust reviewer, cargo-clippy, Rust coding/testing/security rules |
| `sql` | base-only + SQL reviewer, mcp-postgres-safety hook, SQL safety rule, querying-db skill, migration skill |
| `python-sql` | python + sql |
| `typescript-sql` | typescript + sql |
| `fullstack-python` | python + typescript + sql |
| `all` | Every artifact in the manifest (50 total) |

## Individual artifacts

```bash
./install.py --list
```

Lists all 50 artifacts with their ID, type, tags, and description. You can install any combination by ID:

```bash
./install.py --target ~/repos/api --preset python --include stop-review-reminder --exclude plugins-doc
```

Artifact categories:

- **agents** — specialist reviewers and researchers (code-reviewer, security-reviewer, database-reviewer, docs-researcher, doc-updater, python/typescript/go/rust/sql reviewers)
- **hooks** — shell scripts wired into Claude Code events via `settings.json` (PreToolUse safety blocks, PostToolUse linters, Stop review reminder)
- **rules** — Markdown rule fragments loaded via `.claude/rules/` (code review process, safety discipline, style, testing, security, patterns)
- **skills** — user-invokable procedures (`/review`, `/smoke-test`, `/deploy`, `/querying-db`, `/migration`)
- **plugin-docs** — reference list of recommended Claude Code plugins

## Per-language depth

The `base/` layer is fully language-agnostic — it works on any project and doesn't assume any particular runtime or build tool. Language addons in `addons/<lang>/` add:

- A specialist **reviewer agent** trained on the language's idioms, common pitfalls, and ecosystem patterns
- A **lint hook** that runs the language's formatter/checker on every edited file (ruff, biome, svelte-check, golangci-lint, cargo clippy)
- Four **rules files** covering coding style, testing patterns, security pitfalls, and idiomatic patterns

Languages at launch: Python, TypeScript/JavaScript, Go, Rust, and SQL (Postgres-first).

## Conflict handling

When a destination file already exists and `--force` is not set, the installer prompts per file:

```
Conflict: .claude/agents/code-reviewer.md already exists.
[s]kip / [o]verwrite / [d]iff / [a]bort >
```

- **skip** — leave the target unchanged (not added to the receipt)
- **overwrite** — replace with the clank version
- **diff** — print a unified diff, then re-prompt
- **abort** — stop the install (files already copied are not rolled back; receipt is written so `--uninstall` can clean up)

Use `--force` to overwrite all conflicts without prompting. Use `--dry-run` to preview what would change without writing anything. See [docs/install.md](docs/install.md) for the full install sequence and settings.json merge behavior.

## Uninstall

```bash
./install.py --target ~/repos/api --uninstall ruff,python-reviewer
```

Removes the listed artifact files and reverses their `settings.json` fragment entries. The receipt is updated. To uninstall everything, delete `<target>/.claude/` manually.

## Extending clank

- [docs/adding-an-addon.md](docs/adding-an-addon.md) — how to add a new language addon
- [docs/authoring-agents.md](docs/authoring-agents.md) — writing agent definition files
- [docs/authoring-hooks.md](docs/authoring-hooks.md) — writing hook scripts and fragments
- [docs/authoring-skills.md](docs/authoring-skills.md) — writing skill directories
- [docs/authoring-rules.md](docs/authoring-rules.md) — writing rule fragments

Every new artifact must be added to `manifest.toml` — the installer reads the manifest, not the filesystem.

## Running tests

```bash
python3 -m unittest tests.test_install -v
```

Tests live in `tests/test_install.py` and cover manifest loading, lint, selection resolution, copy logic, settings.json merge, install receipt, and uninstall round-trip. CI runs on push and PR via `.github/workflows/test.yml`.

## Layout

```
clank/
├── install.py          # the installer — Python 3.11+, stdlib only
├── manifest.toml       # source of truth for all artifacts and presets
├── base/               # language-agnostic agents, hooks, rules, skills, plugins
│   ├── agents/
│   ├── hooks/
│   ├── rules/
│   ├── skills/
│   ├── plugins/
│   └── settings.fragments/
├── addons/             # per-language specializations (python, typescript, go, rust, sql)
│   ├── python/
│   ├── typescript/
│   ├── go/
│   ├── rust/
│   └── sql/
├── docs/               # authoring guides and install reference (not copied to targets)
├── tests/              # stdlib unittest tests for the installer
│   └── test_install.py
└── .github/workflows/  # CI
    └── test.yml
```

## Credits

clank's content draws from two main sources:

- **ice-scraper** — a production NHL analytics pipeline whose `.claude/` configuration (developed over several months in a live environment) is the origin of `code-reviewer`, `database-reviewer`, the PreToolUse bash/file safety hooks, the stop-review-reminder hook, the base rules, the ruff/biome/svelte-check lint hooks, the mcp-postgres-safety hook, the `querying-db` skill, and the `migration` skill. Generalized here to be language-agnostic.
- **affaan-m/everything-claude-code** — source for the per-language `common-<topic>` rules pattern and for the specialist reviewer agent structure. The addon taxonomy (coding-style / testing / security / patterns per language) follows the split established there.

## License

TBD — add a LICENSE file when ready to publish.
