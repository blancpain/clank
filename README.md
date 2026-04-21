# clank

A template repository of Claude Code customizations — agents, hooks, rules, skills — that you install into new projects with a single command.

## What clank is

clank packages the Claude Code configuration patterns that actually work in production: code-review agents with confidence filtering, PreToolUse safety hooks that block destructive SQL and accidental `rm`, per-language specialist reviewers, and rules that encode hard-won process lessons. Instead of copy-pasting from a prior project every time, you run the installer, pick a preset, and get a fully wired `.claude/` directory in seconds. Everything is configurable — select individual artifacts, exclude what you don't need, or use the interactive picker to browse the catalog before installing.

## Quickstart

One line, from anywhere:

```bash
cd ~/repos/my-project
curl -fsSL https://raw.githubusercontent.com/blancpain/clank/main/install.sh \
  | sh -s -- --interactive
```

clank installs into the current working directory by default and asks `install into <cwd>? [y/N]` before touching anything. `--interactive` opens a curses picker so you can browse every available artifact and check the ones you want. Files land in `./.claude/` and a receipt at `./.claude/.clank-installed.json` records what was installed.

Pin to a specific ref with `CLANK_REF=<branch|tag|sha>`. See [Usage](#usage) for preset bundles and other selection flags.

Prefer a local checkout? Clone once, then run the installer from inside any project directory:

```bash
git clone git@github.com:blancpain/clank.git ~/tools/clank
cd ~/repos/my-project
~/tools/clank/install.py --interactive
```

Same result — skips the `curl | tar` bootstrap.

## Usage

Every example below runs from inside the project directory. `curl | sh -s -- <flags>` works identically.

### Simplest — a preset, CWD default

```bash
./install.py --preset minimal
```
Prompts `y/N` to confirm CWD, then installs `minimal` (core safety hooks + code-reviewer + actions-with-care rule) into `./.claude/`.

### Non-interactive (CI, scripts)

```bash
./install.py --preset python-sql --force
```
`--force` skips the CWD confirmation **and** overwrites existing files on conflict. Use this when there's no TTY or you're sure about overwrites.

### Install somewhere other than CWD

```bash
./install.py --target ~/repos/other-project --preset base-only
```
Explicit `--target` skips the CWD confirm — the flag itself is the confirmation.

### Preview without writing anything

```bash
./install.py --preset python --dry-run
```
Prints the planned copies and `settings.json` merges, touches no files.

### Browse interactively

```bash
./install.py --interactive
```
Opens a curses picker, one page per category (agents, hooks, rules, skills, external skills, MCP servers, plugin docs). Space toggles, `a` toggles all in a category, enter advances.

### Mix a preset with extras or drops

```bash
./install.py --preset python --include stop-review-reminder --exclude plugins-doc
```
`--include` and `--exclude` take comma-separated artifact IDs. `--include` forces an ID in even if it's `default = false` (like `stop-review-reminder`).

### See every available artifact

```bash
./install.py --list
```
Prints every artifact with its ID, type, tags, and description.

### Uninstall

```bash
./install.py --uninstall ruff,python-reviewer
```
Removes the listed artifact files and reverses their `settings.json` fragment entries. Receipt is updated. To wipe everything, delete `.claude/` manually.

### External skills (fetched at install time)

clank supports skills published to [skills.sh](https://skills.sh) that you'd rather pull fresh from upstream than vendor into the repo:

```bash
./install.py --include find-skills --force
```
Shells out to `npx skills add vercel-labs/skills --skill find-skills --copy` inside the project, landing the skill at `./.claude/skills/find-skills/`. Requires Node; the installer warns and skips if `npx` is missing. External skills are `default = false` — you always opt in by ID.

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
| `all` | Every artifact in the manifest |

Artifact categories (run `./install.py --list` to see every ID):

- **agents** — specialist reviewers and researchers (code-reviewer, security-reviewer, database-reviewer, docs-researcher, doc-updater, python/typescript/go/rust/sql reviewers)
- **hooks** — shell scripts wired into Claude Code events via `settings.json` (PreToolUse safety blocks, PostToolUse linters, Stop review reminder)
- **rules** — Markdown rule fragments loaded via `.claude/rules/` (code review process, safety discipline, style, testing, security, patterns)
- **skills** — user-invokable procedures (`/review`, `/smoke-test`, `/deploy`, `/querying-db`, `/migration`)
- **external skills** — fetched from [skills.sh](https://skills.sh) at install time via `npx`
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
