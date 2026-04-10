# clank install reference

## Quick start

```bash
git clone git@github.com:blancpain/clank.git
cd clank
./install.py --target ~/repos/new-project --preset python-sql
```

That copies every artifact for Python + SQL into `~/repos/new-project/.claude/`, merges hook entries into `settings.json`, and writes a receipt at `~/repos/new-project/.claude/.clank-installed.json`.

---

## Requirements

- **Python 3.11+** — the installer uses `tomllib` from the standard library (added in 3.11). No third-party packages required.
- **git** — used to record the clank commit in the install receipt. Optional; install proceeds with commit logged as `unknown` if not found.
- **bash** — all hook scripts are `/bin/bash` scripts.

**Optional tools (auto-detected; clank installs without them — the hooks bail silently if the tool is absent):**

| Tool | Required by |
|------|-------------|
| `jq` | `bash-safety`, `file-safety`, `stop-review-reminder` hooks |
| `ruff` | `ruff` hook (Python addon) |
| `biome` | `biome` hook (TypeScript addon) |
| `svelte-check` | `svelte-check` hook (TypeScript addon) |
| `golangci-lint` | `golangci-lint` hook (Go addon) |
| `cargo` / `clippy` | `cargo-clippy` hook (Rust addon) |

---

## Flags

### `--target <path>` (required unless `--list`)

Absolute or relative path to the project directory to install into. The directory must exist. clank writes only inside `<target>/.claude/`.

```bash
./install.py --target ~/repos/my-project --preset base-only
```

### `--preset <name>`

Install a named bundle from `manifest.toml`. Presets are composable — a preset can include other presets via `@preset:` directives.

Available presets:

| Preset | Contents |
|--------|----------|
| `minimal` | bash-safety, file-safety, code-reviewer, executing-actions-with-care |
| `base-only` | Every artifact tagged `base` |
| `python` | base-only + Python reviewer, ruff hook, Python rules |
| `typescript` | base-only + TypeScript reviewer, biome, svelte-check, TypeScript rules |
| `go` | base-only + Go reviewer, golangci-lint, Go rules |
| `rust` | base-only + Rust reviewer, cargo-clippy, Rust rules |
| `sql` | base-only + SQL reviewer, mcp-postgres-safety hook, SQL rules, querying-db skill, migration skill |
| `python-sql` | python + sql |
| `typescript-sql` | typescript + sql |
| `fullstack-python` | python + typescript + sql |
| `all` | Every artifact in the manifest |

```bash
./install.py --target ~/repos/api --preset python-sql
```

### `--include <id1,id2,...>`

Add specific artifact IDs to the selection, composable with `--preset`. Use `./install.py --list` to see all IDs.

```bash
# Install the python preset, then also add the stop-review-reminder hook
./install.py --target ~/repos/api --preset python --include stop-review-reminder
```

### `--exclude <id1,id2,...>`

Remove artifact IDs from the current selection. Applied after preset expansion and `--include`.

```bash
# Install base-only but skip the plugin doc
./install.py --target ~/repos/api --preset base-only --exclude plugins-doc
```

### `-i` / `--interactive`

Opens a numbered-list picker grouped by category (Agents, Hooks, Rules, Skills, Plugin docs). Toggle items with numbers, `a` for all in category, `n` for none, `c` to continue to next category. Composable with `--preset` or `--include` to pre-select items.

```bash
./install.py --target ~/repos/api --interactive
```

Interactive session example:

```
== Agents ==
  [ ]  1. code-reviewer               — Language-agnostic code reviewer
  [ ]  2. database-reviewer           — Postgres database integrity auditor
Toggle (numbers), (a)ll, (n)one, (c)ontinue > 1 2
== Hooks ==
  [ ]  1. bash-safety                 — PreToolUse Bash guardrails
Toggle (numbers), (a)ll, (n)one, (c)ontinue > a
== Hooks ==
  [x]  1. bash-safety                 — PreToolUse Bash guardrails
Toggle (numbers), (a)ll, (n)one, (c)ontinue > c
```

### `--dry-run`

Print what would be copied and exit without writing anything. Useful for previewing a preset before committing.

```bash
./install.py --target ~/repos/api --preset python --dry-run
```

Output:

```
[dry-run] copy base/agents/code-reviewer.md -> /home/user/repos/api/.claude/agents/code-reviewer.md
[dry-run] copy addons/python/hooks/ruff-check.sh -> /home/user/repos/api/.claude/hooks/ruff-check.sh
...
```

### `--force`

Overwrite all conflicts without prompting. Useful for re-running the installer after updating clank to get fresh versions of all artifacts.

```bash
./install.py --target ~/repos/api --preset python --force
```

`--force` also skips the stop-hook opt-in prompt (defaults to "no" unless `stop-review-reminder` was explicitly passed via `--include`).

### `--list`

Print every artifact in the manifest and exit. Shows ID, type, tags, and description.

```bash
./install.py --list
```

Output (excerpt):

```
code-reviewer                  [agent     ] (base,review) — Language-agnostic code reviewer
bash-safety                    [hook      ] (base,safety) — PreToolUse Bash guardrails
ruff                           [hook      ] (python,lint) — PostToolUse ruff check on edited Python files
```

### `--uninstall <id1,id2,...>`

Remove listed artifacts from `--target` and reverse their settings.json fragments. Requires `--target`.

```bash
./install.py --target ~/repos/api --uninstall ruff,python-reviewer
```

### `--version`

Print the clank version and exit.

```bash
./install.py --version
# clank 0.1.0
```

---

## Install sequence

When you run the installer, the following happens in order:

1. **Parse args and load manifest.** `manifest.toml` is read and validated. If any lint error is found (missing file, duplicate ID, broken preset reference), the installer aborts before touching the target.

2. **Resolve selection.** Preset directives (`@preset:`, `@tag:`, `@tag:*`) are recursively expanded into a flat set of artifact IDs. `--include` IDs are unioned in. `--exclude` IDs are discarded. Artifacts with `default = false` are excluded from preset/tag expansion (they only enter via explicit `--include`).

3. **Safety checks.** The target must exist and be a directory. If `manifest.toml` and a `base/` directory are found at the target root, the installer refuses to run (this would be installing clank into itself). `<target>/.claude/` is created if it doesn't exist.

4. **Stop-hook prompt.** Unless `--force` or `--dry-run`, the installer asks once:
   ```
   Include the stop hook that reminds you to run code-reviewer on code changes? [y/N]
   ```
   Answering `y` adds `stop-review-reminder` to the selection. This artifact's `default = false` flag prevents it from being pulled in silently by any preset.

5. **Copy files.** For each selected artifact, the source path is mapped to a destination under `<target>/.claude/` by stripping the `base/` or `addons/<name>/` prefix. Skills (directories) are copied recursively, file by file. Hooks have their executable bit set after copying. Conflicts are handled per-file (see below).

6. **Merge settings fragments.** For each copied artifact that declares a `settings_fragment`, the JSON fragment is deep-merged into `<target>/.claude/settings.json`. If no `settings.json` exists, one is seeded from `base/settings.json` first.

7. **Write install receipt.** `<target>/.claude/.clank-installed.json` is written (or updated) with the list of installed artifact IDs.

8. **Print summary.** Lists what was installed and what was skipped, plus soft warnings for `requires_mcp` hints (e.g. `database-reviewer` expects a `postgres` MCP server configured in `.mcp.json`).

---

## Selection semantics

**Preset expansion** resolves recursively. `@preset:python` expands `@preset:base-only`, which expands `@tag:base` to every artifact tagged `base`. Cycles are detected and rejected.

**`@tag:*`** selects every artifact in the manifest, including those in addons. This is what `all` uses.

**`default = false`** marks an artifact that should never be pulled in by preset or tag expansion — only by an explicit `--include <id>`. Currently only `stop-review-reminder` uses this flag. It still appears in `--list` output.

**Composition example:**

```bash
# Start with python preset, add the stop hook explicitly, drop the plugin doc
./install.py --target ~/repos/api \
  --preset python \
  --include stop-review-reminder \
  --exclude plugins-doc
```

---

## Conflict handling

When a destination file already exists and `--force` is not set, the installer prompts:

```
Conflict: .claude/agents/code-reviewer.md already exists.
[s]kip / [o]verwrite / [d]iff / [a]bort >
```

- **skip** — leave the target file unchanged. The artifact ID is not added to the receipt.
- **overwrite** — replace the target file with the clank version.
- **diff** — print a unified diff between the clank source and the target file, then re-prompt.
- **abort** — stop the install. Files already copied in this run are NOT rolled back. A partial receipt is written so `--uninstall` can clean up.

`--force` silently picks `overwrite` for every conflict.

`--dry-run` lists conflicts without prompting (no writes occur).

---

## settings.json merge behavior

clank additively merges hook fragments into the target's existing `settings.json`. The target always wins on scalar conflicts; clank only adds, never overwrites.

**Hook arrays** merge by `matcher`. For each fragment entry:
- If the target has an entry with the same `matcher`, clank appends only the new `hooks[]` items (deduped by `command` string).
- If no matching entry exists, the entire fragment entry is appended.

**permissions.allow / permissions.deny** are set-unioned — clank adds its entries without removing any that the target already has.

**Re-runs are idempotent.** Running the installer twice produces the same `settings.json` because dedupe-by-command prevents duplicate hook entries.

**Example:** If your `settings.json` already has a `PostToolUse / Edit|Write` entry running your own linter, installing the `ruff` hook appends `ruff-check.sh` to that same matcher group rather than creating a second group.

---

## Install receipt format

After a successful install, clank writes:

```
<target>/.claude/.clank-installed.json
```

Structure:

```json
{
  "clank_version": "0.1.0",
  "clank_commit": "a1b2c3d4e5f6",
  "installed_at": "2026-04-10T12:34:56.789012+00:00",
  "target": "/absolute/path/to/project",
  "artifacts": [
    "bash-safety",
    "code-reviewer",
    "file-safety",
    "python-coding-style",
    "python-patterns",
    "python-reviewer",
    "python-security",
    "python-testing",
    "ruff"
  ]
}
```

- `clank_version` — the installer version (`__version__` in `install.py`)
- `clank_commit` — the git SHA of the clank repo at install time (first 12 chars), or `"unknown"` if git is unavailable
- `installed_at` — ISO 8601 timestamp in UTC
- `target` — resolved absolute path of the target directory
- `artifacts` — sorted list of artifact IDs that were copied. IDs that were skipped at the conflict prompt are not listed. Re-running the installer merges into this list.

---

## Uninstall workflow

```bash
./install.py --target ~/repos/api --uninstall ruff,python-reviewer
```

For each listed artifact ID, the uninstaller:

1. Removes the file (or directory for skills) at its computed destination.
2. Reverse-merges the artifact's `settings_fragment` from `<target>/.claude/settings.json` — removes the specific `command` entries from matching `matcher` groups, removes the group if empty, removes matching `permissions` entries.
3. Updates the receipt to remove the uninstalled IDs. If the receipt is now empty (all artifacts removed), the receipt file is deleted.

**To uninstall everything:** Delete `<target>/.claude/` manually. clank has no state outside that directory.

---

## Safety guarantees

- **Never writes outside `<target>/.claude/`.** All artifacts land under `.claude/`. The receipt lives at `.claude/.clank-installed.json`. No files are written at the target repo root.
- **Never touches `CLAUDE.md`.** The target's `CLAUDE.md` (at any level) is never read or written by the installer.
- **Never deletes files not in the receipt.** `--uninstall` only removes IDs that appear in `.clank-installed.json`.
- **Refuses to install into itself.** If `--target` has both a `manifest.toml` and a `base/` directory at its root, the installer aborts with `"refusing to install into clank itself"`.
- **Aborts before writes on manifest lint failure.** If `manifest.toml` fails validation (missing path, duplicate ID, broken preset reference), the installer exits before copying anything.

---

## FAQ

**Q: What if I already have a `.claude/settings.json`?**

clank reads your existing `settings.json` and merges additively. Your existing hook entries, permissions, and other settings are preserved. clank never overwrites scalar keys that already exist in your file. To preview file copies without making changes, run with `--dry-run` first.

**Q: How do I uninstall everything?**

Delete `<target>/.claude/` manually, or pass all IDs from the receipt to `--uninstall`. Either method leaves a clean slate.

**Q: Can I re-run the installer safely?**

Yes. Hook entries in `settings.json` are deduped by `command`, so running the installer twice won't create duplicate hook entries. File copies prompt for conflicts unless you pass `--force`. The receipt is union-merged, so previously installed IDs stay listed.

**Q: What if I delete the receipt file?**

The installer loses track of what was previously installed, so `--uninstall` won't know which IDs to remove. File artifacts remain in place. You can delete files from `.claude/agents/`, `.claude/hooks/`, etc. and clean up `settings.json` by hand. To re-establish tracking, run the installer again with the same preset — it will prompt for conflicts on files that already exist.
