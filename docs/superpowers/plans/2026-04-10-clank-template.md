# Clank Template Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build out the `clank` repo as a Claude Code template: a Python installer + manifest + base artifacts + 5 language addons + docs + CI, per the design spec at `docs/superpowers/specs/2026-04-10-clank-template-design.md`.

**Architecture:** Two-layer template (`base/` + `addons/<lang>/`) merged into a target project's `.claude/` directory by a stdlib-only Python 3.11+ installer driven by a `manifest.toml`. The installer handles selection resolution (presets/tags/includes/excludes), conflict-prompt UX, settings.json deep-merge, and uninstall. Content artifacts are lifted from ice-scraper's `.claude/` (stripped of project specifics) and affaan-m/everything-claude-code (per-language common rules).

**Tech Stack:** Python 3.11+ stdlib only (`tomllib`, `argparse`, `shutil`, `json`, `pathlib`, `unittest`), Bash for hook scripts, Markdown for all content artifacts, GitHub Actions for CI.

---

## Context for every task

Every subagent executing a task from this plan must read:

1. **The design spec** — `docs/superpowers/specs/2026-04-10-clank-template-design.md`. This is the source of truth for what each artifact contains and how the installer should behave.
2. **This plan file** — for the specific task they're executing.
3. **The source material for lifted artifacts** — stated per task. Usually either `/Users/yasen.dimitrov.ext/repos/ice-scraper/.claude/...` (for ice-scraper-lifted content) or fetched via `gh api` from `affaan-m/everything-claude-code` (for affaan-m-lifted content).

Commits are made by the subagent as each task completes. Use the project's code-reviewer agent (which doesn't exist yet) — so until Phase 2 ships that agent, subagents proceed without the code-reviewer step and the main thread reviews each task manually.

---

# Phase 1 — Repo bootstrap + installer core

Phase 1 delivers a working installer against a stub manifest. No content artifacts yet — the installer is validated end-to-end with a hand-crafted fixture manifest in tests before any real content gets wired up.

## Task 1.1: Repo scaffolding

**Files:**
- Create: `/Users/yasen.dimitrov.ext/repos/clank/.gitignore`
- Create: `/Users/yasen.dimitrov.ext/repos/clank/base/` (empty directory with `.gitkeep`)
- Create: `/Users/yasen.dimitrov.ext/repos/clank/base/agents/.gitkeep`
- Create: `/Users/yasen.dimitrov.ext/repos/clank/base/hooks/.gitkeep`
- Create: `/Users/yasen.dimitrov.ext/repos/clank/base/rules/.gitkeep`
- Create: `/Users/yasen.dimitrov.ext/repos/clank/base/skills/.gitkeep`
- Create: `/Users/yasen.dimitrov.ext/repos/clank/base/plugins/.gitkeep`
- Create: `/Users/yasen.dimitrov.ext/repos/clank/base/settings.fragments/.gitkeep`
- Create: `/Users/yasen.dimitrov.ext/repos/clank/addons/python/{agents,hooks,rules,skills,settings.fragments}/.gitkeep`
- Create: `/Users/yasen.dimitrov.ext/repos/clank/addons/typescript/{agents,hooks,rules,skills,settings.fragments}/.gitkeep`
- Create: `/Users/yasen.dimitrov.ext/repos/clank/addons/go/{agents,hooks,rules,skills,settings.fragments}/.gitkeep`
- Create: `/Users/yasen.dimitrov.ext/repos/clank/addons/rust/{agents,hooks,rules,skills,settings.fragments}/.gitkeep`
- Create: `/Users/yasen.dimitrov.ext/repos/clank/addons/sql/{agents,hooks,rules,skills,settings.fragments}/.gitkeep`
- Create: `/Users/yasen.dimitrov.ext/repos/clank/tests/.gitkeep`
- Create: `/Users/yasen.dimitrov.ext/repos/clank/.github/workflows/.gitkeep`
- Create: `/Users/yasen.dimitrov.ext/repos/clank/docs/{authoring-agents.md,authoring-hooks.md,authoring-skills.md,authoring-rules.md,install.md,adding-an-addon.md}` as empty stubs (will be filled in Phase 4)

- [ ] **Step 1: Create the directory tree**

```bash
cd /Users/yasen.dimitrov.ext/repos/clank
mkdir -p base/{agents,hooks,rules,skills,plugins,settings.fragments}
for addon in python typescript go rust sql; do
  mkdir -p "addons/$addon"/{agents,hooks,rules,skills,settings.fragments}
done
mkdir -p tests .github/workflows docs
for d in base/agents base/hooks base/rules base/skills base/plugins base/settings.fragments \
         addons/python/agents addons/python/hooks addons/python/rules addons/python/skills addons/python/settings.fragments \
         addons/typescript/agents addons/typescript/hooks addons/typescript/rules addons/typescript/skills addons/typescript/settings.fragments \
         addons/go/agents addons/go/hooks addons/go/rules addons/go/skills addons/go/settings.fragments \
         addons/rust/agents addons/rust/hooks addons/rust/rules addons/rust/skills addons/rust/settings.fragments \
         addons/sql/agents addons/sql/hooks addons/sql/rules addons/sql/skills addons/sql/settings.fragments \
         tests .github/workflows; do
  touch "$d/.gitkeep"
done
```

- [ ] **Step 2: Write `.gitignore`**

```
# Python
__pycache__/
*.py[cod]
*$py.class
*.egg-info/
.venv/
venv/

# Test scratch
tests/tmp/
tests/.clank-test-*/

# Editor noise
.vscode/
.idea/
*.swp
*.swo
.DS_Store
```

- [ ] **Step 3: Commit the scaffolding**

```bash
cd /Users/yasen.dimitrov.ext/repos/clank
git add .gitignore base/ addons/ tests/ .github/ docs/
git commit -m "chore: scaffold clank directory structure

Create base/, addons/{python,typescript,go,rust,sql}/, tests/, docs/,
and .github/workflows/ with .gitkeep placeholders so the tree is
committable before content exists."
```

---

## Task 1.2: Minimal `manifest.toml`

Ship a schema-valid manifest with ZERO real artifacts. Phase 1's installer tests will supply a fixture manifest; this committed file just defines the schema so Phase 2 can append to it.

**Files:**
- Create: `/Users/yasen.dimitrov.ext/repos/clank/manifest.toml`

- [ ] **Step 1: Write the manifest**

```toml
# clank — Claude Code template installer manifest
#
# This file is the source of truth for every artifact (agent, hook, rule,
# skill, plugin-doc) clank knows how to install, and for every preset that
# bundles artifacts into common install configurations.
#
# Schema:
#   version              — manifest schema version, currently 1
#   [[artifacts]]        — one block per artifact:
#     id                 — stable string identifier, unique across the manifest
#     type               — "agent" | "hook" | "rule" | "skill" | "plugin-doc"
#     path               — file path relative to clank root; directory path for skills
#     description        — human-readable one-liner for --list and install summary
#     tags               — list of strings; used by @tag:<name> expansion in presets
#     settings_fragment  — (optional) path to the hook's settings.json fragment
#     default            — (optional) bool; false excludes from @tag/@preset expansion
#     requires_mcp       — (optional) list of MCP server names; soft hint only
#
#   [presets]            — map of preset name -> list of member selectors
#     Selectors: artifact ID, "@preset:<name>", "@tag:<name>", or "@tag:*"

version = 1

artifacts = []

[presets]
```

- [ ] **Step 2: Commit**

```bash
cd /Users/yasen.dimitrov.ext/repos/clank
git add manifest.toml
git commit -m "feat: add empty manifest.toml with schema comments

Reserve the filename, document the schema, and leave artifacts empty so
Phase 2 content tasks can append without touching structure."
```

---

## Task 1.3: `install.py` — CLI skeleton + tests

Start the installer with `argparse` wiring and a no-op `main()`. Tests assert the CLI accepts the documented flags and returns the right exit codes on bad input.

**Files:**
- Create: `/Users/yasen.dimitrov.ext/repos/clank/install.py`
- Create: `/Users/yasen.dimitrov.ext/repos/clank/tests/test_install.py`

- [ ] **Step 1: Write the failing test file**

```python
"""Tests for install.py."""
import subprocess
import sys
import unittest
from pathlib import Path

CLANK_ROOT = Path(__file__).resolve().parent.parent
INSTALL_PY = CLANK_ROOT / "install.py"


def run_install(*args, input_text=None):
    """Run install.py as a subprocess and return (returncode, stdout, stderr)."""
    proc = subprocess.run(
        [sys.executable, str(INSTALL_PY), *args],
        input=input_text,
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


class TestCLI(unittest.TestCase):
    def test_version_flag(self):
        rc, out, _ = run_install("--version")
        self.assertEqual(rc, 0)
        self.assertIn("clank", out)

    def test_no_args_shows_help_and_fails(self):
        rc, _, err = run_install()
        self.assertNotEqual(rc, 0)
        self.assertIn("--target", err)

    def test_help_flag(self):
        rc, out, _ = run_install("--help")
        self.assertEqual(rc, 0)
        self.assertIn("--preset", out)
        self.assertIn("--include", out)
        self.assertIn("--exclude", out)
        self.assertIn("--uninstall", out)
        self.assertIn("--dry-run", out)
        self.assertIn("--force", out)
        self.assertIn("--list", out)
        self.assertIn("--interactive", out)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test and verify it fails (install.py doesn't exist)**

```bash
cd /Users/yasen.dimitrov.ext/repos/clank
python -m unittest tests.test_install -v
```

Expected: ERROR because `install.py` doesn't exist yet.

- [ ] **Step 3: Write `install.py` CLI skeleton**

```python
#!/usr/bin/env python3
"""clank — Claude Code template installer.

Copies base + addon artifacts into a target project's .claude/ directory,
merges settings.json fragments, and manages install receipts for uninstall.

See docs/install.md for full reference.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

__version__ = "0.1.0"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="clank",
        description="Install clank .claude/ artifacts into a project",
    )
    parser.add_argument("--target", type=Path, help="Target project directory")
    parser.add_argument("--preset", help="Named bundle from manifest.toml")
    parser.add_argument("--include", help="Comma-separated artifact IDs to add")
    parser.add_argument("--exclude", help="Comma-separated artifact IDs to drop")
    parser.add_argument(
        "-i", "--interactive", action="store_true",
        help="Pick artifacts via numbered-list prompt",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print what would be copied, write nothing",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Overwrite conflicts without prompting",
    )
    parser.add_argument(
        "--list", action="store_true",
        help="Print the manifest and exit",
    )
    parser.add_argument(
        "--uninstall",
        help="Comma-separated artifact IDs to uninstall from --target",
    )
    parser.add_argument(
        "--version", action="version", version=f"clank {__version__}",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.target and not args.list:
        parser.error("--target is required unless --list is given")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests and verify they pass**

```bash
cd /Users/yasen.dimitrov.ext/repos/clank
python -m unittest tests.test_install -v
```

Expected: `test_version_flag`, `test_no_args_shows_help_and_fails`, `test_help_flag` all PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/yasen.dimitrov.ext/repos/clank
git add install.py tests/test_install.py
git commit -m "feat(installer): add install.py CLI skeleton

Argparse wiring for every documented flag (--target, --preset, --include,
--exclude, --interactive, --dry-run, --force, --list, --uninstall,
--version). main() is a no-op; subsequent tasks wire up the real logic."
```

---

## Task 1.4: `install.py` — manifest loading + lint

Add `Manifest.load()` and `lint_manifest()` so the installer can parse `manifest.toml` and validate it before any file operations. Tests use a fixture manifest in `tests/fixtures/`.

**Files:**
- Modify: `/Users/yasen.dimitrov.ext/repos/clank/install.py`
- Modify: `/Users/yasen.dimitrov.ext/repos/clank/tests/test_install.py`
- Create: `/Users/yasen.dimitrov.ext/repos/clank/tests/fixtures/manifest_valid.toml`
- Create: `/Users/yasen.dimitrov.ext/repos/clank/tests/fixtures/manifest_bad_dup_id.toml`
- Create: `/Users/yasen.dimitrov.ext/repos/clank/tests/fixtures/manifest_bad_missing_path.toml`
- Create: `/Users/yasen.dimitrov.ext/repos/clank/tests/fixtures/base/agents/stub-agent.md` (fixture content file)
- Create: `/Users/yasen.dimitrov.ext/repos/clank/tests/fixtures/base/hooks/stub-hook.sh` (fixture content file)
- Create: `/Users/yasen.dimitrov.ext/repos/clank/tests/fixtures/base/settings.fragments/stub-hook.json`

- [ ] **Step 1: Create fixture files**

```bash
cd /Users/yasen.dimitrov.ext/repos/clank
mkdir -p tests/fixtures/base/{agents,hooks,settings.fragments}
```

Write `tests/fixtures/base/agents/stub-agent.md`:
```markdown
---
name: stub-agent
description: Stub agent for installer tests
---

Stub body.
```

Write `tests/fixtures/base/hooks/stub-hook.sh`:
```bash
#!/bin/bash
# Stub hook for installer tests
exit 0
```

Make it executable:
```bash
chmod +x tests/fixtures/base/hooks/stub-hook.sh
```

Write `tests/fixtures/base/settings.fragments/stub-hook.json`:
```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/stub-hook.sh"
          }
        ]
      }
    ]
  }
}
```

Write `tests/fixtures/manifest_valid.toml`:
```toml
version = 1

[[artifacts]]
id = "stub-agent"
type = "agent"
path = "base/agents/stub-agent.md"
description = "Stub agent for installer tests"
tags = ["base", "test"]

[[artifacts]]
id = "stub-hook"
type = "hook"
path = "base/hooks/stub-hook.sh"
settings_fragment = "base/settings.fragments/stub-hook.json"
description = "Stub hook"
tags = ["base", "test"]

[presets]
minimal = ["stub-agent"]
all = ["@tag:*"]
test-both = ["stub-agent", "stub-hook"]
```

Write `tests/fixtures/manifest_bad_dup_id.toml`:
```toml
version = 1

[[artifacts]]
id = "dup"
type = "agent"
path = "base/agents/stub-agent.md"
description = "first"
tags = []

[[artifacts]]
id = "dup"
type = "agent"
path = "base/agents/stub-agent.md"
description = "second"
tags = []
```

Write `tests/fixtures/manifest_bad_missing_path.toml`:
```toml
version = 1

[[artifacts]]
id = "missing"
type = "agent"
path = "base/agents/does-not-exist.md"
description = "references nonexistent file"
tags = []
```

- [ ] **Step 2: Write failing tests for manifest loading and lint**

Append to `tests/test_install.py`:

```python
# Import functions directly from install.py for unit tests.
# Requires install.py to be importable — pathing added at the top of the file.
sys.path.insert(0, str(CLANK_ROOT))
import install  # noqa: E402


FIXTURES = CLANK_ROOT / "tests" / "fixtures"


class TestManifestLoading(unittest.TestCase):
    def test_load_valid_manifest(self):
        m = install.Manifest.load(FIXTURES / "manifest_valid.toml")
        self.assertEqual(m.version, 1)
        self.assertIn("stub-agent", m.artifacts)
        self.assertIn("stub-hook", m.artifacts)
        self.assertEqual(m.artifacts["stub-agent"]["type"], "agent")
        self.assertIn("minimal", m.presets)
        self.assertEqual(m.presets["minimal"], ["stub-agent"])


class TestManifestLint(unittest.TestCase):
    def test_valid_manifest_lints_clean(self):
        m = install.Manifest.load(FIXTURES / "manifest_valid.toml")
        errors = install.lint_manifest(m, FIXTURES)
        self.assertEqual(errors, [])

    def test_duplicate_ids_rejected(self):
        m = install.Manifest.load(FIXTURES / "manifest_bad_dup_id.toml")
        errors = install.lint_manifest(m, FIXTURES)
        self.assertTrue(any("duplicate" in e for e in errors))

    def test_missing_path_rejected(self):
        m = install.Manifest.load(FIXTURES / "manifest_bad_missing_path.toml")
        errors = install.lint_manifest(m, FIXTURES)
        self.assertTrue(any("does not exist" in e for e in errors))
```

- [ ] **Step 3: Run tests and verify they fail**

```bash
cd /Users/yasen.dimitrov.ext/repos/clank
python -m unittest tests.test_install -v
```

Expected: The three new tests FAIL with `AttributeError: module 'install' has no attribute 'Manifest'`.

Note on fixture loading: `tomllib` in Python will parse `[[artifacts]]` into a list of dicts. When a file has duplicate top-level keys it actually errors — but duplicate *array-of-tables* entries are allowed. To make `manifest_bad_dup_id.toml` parse and still trigger the duplicate-ID check, use two valid `[[artifacts]]` blocks with the same `id` field (which is what the fixture above does — duplicate `id` values inside different array entries are parseable but lint-rejectable).

- [ ] **Step 4: Implement `Manifest.load()` and `lint_manifest()`**

Append to `install.py` (after `__version__`):

```python
import json
import tomllib


VALID_TYPES = {"agent", "hook", "rule", "skill", "plugin-doc"}


class Manifest:
    def __init__(self, artifacts: list[dict], presets: dict[str, list[str]], version: int):
        duplicate_ids = sorted({a["id"] for a in artifacts if [x["id"] for x in artifacts].count(a["id"]) > 1})
        self._duplicate_ids = duplicate_ids
        self.artifacts = {a["id"]: a for a in artifacts}
        self.presets = presets
        self.version = version

    @classmethod
    def load(cls, path: Path) -> "Manifest":
        with open(path, "rb") as f:
            data = tomllib.load(f)
        return cls(
            artifacts=data.get("artifacts", []),
            presets=data.get("presets", {}),
            version=data.get("version", 0),
        )


def lint_manifest(manifest: Manifest, clank_root: Path) -> list[str]:
    errors: list[str] = []

    if manifest.version != 1:
        errors.append(f"manifest version must be 1, got {manifest.version}")

    if manifest._duplicate_ids:
        errors.append(f"duplicate artifact IDs: {manifest._duplicate_ids}")

    for aid, artifact in manifest.artifacts.items():
        if artifact.get("type") not in VALID_TYPES:
            errors.append(f"{aid}: invalid type {artifact.get('type')!r}")

        src = clank_root / artifact["path"]
        if not src.exists():
            errors.append(f"{aid}: path does not exist: {artifact['path']}")

        if artifact.get("type") == "skill" and src.exists() and not src.is_dir():
            errors.append(f"{aid}: skill path must be a directory, got file: {artifact['path']}")

        frag = artifact.get("settings_fragment")
        if frag:
            frag_path = clank_root / frag
            if not frag_path.exists():
                errors.append(f"{aid}: settings_fragment does not exist: {frag}")
            else:
                try:
                    json.loads(frag_path.read_text())
                except json.JSONDecodeError as e:
                    errors.append(f"{aid}: settings_fragment invalid JSON: {e}")

    known_ids = set(manifest.artifacts.keys())
    preset_names = set(manifest.presets.keys())
    for preset_name, members in manifest.presets.items():
        for member in members:
            if member.startswith("@preset:"):
                ref = member[len("@preset:"):]
                if ref not in preset_names:
                    errors.append(f"preset {preset_name!r}: references unknown preset {ref!r}")
            elif member.startswith("@tag:"):
                pass  # any tag is allowed; @tag:* is the catch-all
            elif member not in known_ids:
                errors.append(f"preset {preset_name!r}: references unknown artifact {member!r}")

    return errors
```

- [ ] **Step 5: Run tests, verify pass**

```bash
cd /Users/yasen.dimitrov.ext/repos/clank
python -m unittest tests.test_install -v
```

Expected: All 6 tests (3 CLI + 3 manifest) PASS.

- [ ] **Step 6: Commit**

```bash
cd /Users/yasen.dimitrov.ext/repos/clank
git add install.py tests/test_install.py tests/fixtures/
git commit -m "feat(installer): add manifest loading + lint

Manifest.load() parses manifest.toml via tomllib. lint_manifest() checks
version, duplicate IDs, artifact types, path existence, skill-path-is-dir,
settings_fragment validity, and preset reference integrity. Tests use
fixture manifests + fixture content files in tests/fixtures/."
```

---

## Task 1.5: `install.py` — selection resolution

Add the preset/tag/include/exclude resolver that turns user input into a flat set of artifact IDs.

**Files:**
- Modify: `/Users/yasen.dimitrov.ext/repos/clank/install.py`
- Modify: `/Users/yasen.dimitrov.ext/repos/clank/tests/test_install.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_install.py`:

```python
class TestSelectionResolution(unittest.TestCase):
    def setUp(self):
        self.manifest = install.Manifest.load(FIXTURES / "manifest_valid.toml")

    def test_resolve_preset_minimal(self):
        selected = install.resolve_selection(self.manifest, preset="minimal")
        self.assertEqual(selected, {"stub-agent"})

    def test_resolve_tag_star(self):
        selected = install.resolve_selection(self.manifest, preset="all")
        self.assertEqual(selected, {"stub-agent", "stub-hook"})

    def test_resolve_include_only(self):
        selected = install.resolve_selection(self.manifest, include=["stub-hook"])
        self.assertEqual(selected, {"stub-hook"})

    def test_resolve_preset_plus_include(self):
        selected = install.resolve_selection(
            self.manifest, preset="minimal", include=["stub-hook"]
        )
        self.assertEqual(selected, {"stub-agent", "stub-hook"})

    def test_resolve_preset_minus_exclude(self):
        selected = install.resolve_selection(
            self.manifest, preset="all", exclude=["stub-hook"]
        )
        self.assertEqual(selected, {"stub-agent"})

    def test_resolve_unknown_preset_raises(self):
        with self.assertRaises(ValueError):
            install.resolve_selection(self.manifest, preset="nonexistent")

    def test_resolve_unknown_include_raises(self):
        with self.assertRaises(ValueError):
            install.resolve_selection(self.manifest, include=["nonexistent"])
```

- [ ] **Step 2: Verify tests fail**

```bash
python -m unittest tests.test_install -v
```

Expected: 7 new tests FAIL with `AttributeError`.

- [ ] **Step 3: Implement the resolver**

Append to `install.py`:

```python
def resolve_selection(
    manifest: Manifest,
    preset: str | None = None,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
) -> set[str]:
    """Resolve a user selection into a flat set of artifact IDs.

    Honors the default=false flag: such artifacts are excluded from
    @tag/@preset expansion, but explicit --include overrides this.
    """
    selected: set[str] = set()
    explicit_includes = set(include or [])

    if preset:
        selected |= _expand_preset(manifest, preset)

    for aid in explicit_includes:
        if aid not in manifest.artifacts:
            raise ValueError(f"unknown artifact: {aid}")
        selected.add(aid)

    for aid in exclude or []:
        selected.discard(aid)

    # Strip default=false artifacts unless explicitly included
    filtered = set()
    for aid in selected:
        if manifest.artifacts[aid].get("default") is False and aid not in explicit_includes:
            continue
        filtered.add(aid)
    return filtered


def _expand_preset(
    manifest: Manifest,
    name: str,
    _seen: set[str] | None = None,
) -> set[str]:
    if _seen is None:
        _seen = set()
    if name in _seen:
        raise ValueError(f"circular preset reference: {name}")
    if name not in manifest.presets:
        raise ValueError(f"unknown preset: {name}")
    _seen = _seen | {name}

    result: set[str] = set()
    for member in manifest.presets[name]:
        if member.startswith("@preset:"):
            result |= _expand_preset(manifest, member[len("@preset:"):], _seen)
        elif member == "@tag:*":
            result |= {aid for aid in manifest.artifacts}
        elif member.startswith("@tag:"):
            tag = member[len("@tag:"):]
            result |= {
                aid for aid, a in manifest.artifacts.items()
                if tag in a.get("tags", [])
            }
        else:
            if member not in manifest.artifacts:
                raise ValueError(f"preset {name}: unknown artifact {member}")
            result.add(member)
    return result
```

- [ ] **Step 4: Run tests, verify pass**

```bash
python -m unittest tests.test_install -v
```

Expected: All 13 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add install.py tests/test_install.py
git commit -m "feat(installer): add selection resolver

resolve_selection() expands presets, @tag/@preset directives, --include,
and --exclude into a flat set of artifact IDs. Filters out default=false
artifacts unless explicitly included. Detects circular preset references."
```

---

## Task 1.6: `install.py` — safety checks + target setup

Add pre-flight safety checks: target must exist, target must not be clank itself, `<target>/.claude/` is created if missing.

**Files:**
- Modify: `/Users/yasen.dimitrov.ext/repos/clank/install.py`
- Modify: `/Users/yasen.dimitrov.ext/repos/clank/tests/test_install.py`

- [ ] **Step 1: Write failing tests**

```python
import tempfile

class TestSafetyChecks(unittest.TestCase):
    def test_nonexistent_target_raises(self):
        with self.assertRaises(install.InstallError):
            install.check_target(Path("/nonexistent/path/to/target"))

    def test_target_is_clank_itself_raises(self):
        with self.assertRaises(install.InstallError) as ctx:
            install.check_target(CLANK_ROOT)
        self.assertIn("clank itself", str(ctx.exception))

    def test_valid_target_creates_claude_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            install.check_target(target)
            self.assertTrue((target / ".claude").is_dir())
```

- [ ] **Step 2: Verify failure**

```bash
python -m unittest tests.test_install -v
```

- [ ] **Step 3: Implement**

Append to `install.py`:

```python
class InstallError(Exception):
    """Raised when the installer cannot proceed safely."""


def check_target(target: Path) -> None:
    """Validate the target directory and create .claude/ if missing."""
    if not target.exists():
        raise InstallError(f"target does not exist: {target}")
    if not target.is_dir():
        raise InstallError(f"target is not a directory: {target}")
    if (target / "manifest.toml").exists() and (target / "base").is_dir():
        raise InstallError(
            f"refusing to install into clank itself: {target}"
        )
    (target / ".claude").mkdir(exist_ok=True)
```

- [ ] **Step 4: Run tests**

Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add install.py tests/test_install.py
git commit -m "feat(installer): add target safety checks

check_target() validates the target exists, is a directory, is not clank
itself (detected via manifest.toml + base/ presence), and ensures
<target>/.claude/ exists."
```

---

## Task 1.7: `install.py` — file/directory copy + conflict handling

Implement `copy_artifact()` with per-file conflict resolution via a callback. Conflict UX (`skip`/`overwrite`/`diff`/`abort`) is exposed as `prompt_on_conflict()` but tests use a mock callback.

**Files:**
- Modify: `/Users/yasen.dimitrov.ext/repos/clank/install.py`
- Modify: `/Users/yasen.dimitrov.ext/repos/clank/tests/test_install.py`

- [ ] **Step 1: Write failing tests**

```python
class TestCopyArtifact(unittest.TestCase):
    def setUp(self):
        self.manifest = install.Manifest.load(FIXTURES / "manifest_valid.toml")
        self.tmp = tempfile.TemporaryDirectory()
        self.target = Path(self.tmp.name)
        (self.target / ".claude").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_copy_agent_file(self):
        install.copy_artifact(
            self.manifest.artifacts["stub-agent"],
            FIXTURES,
            self.target,
            on_conflict=lambda dst: "overwrite",
        )
        dst = self.target / ".claude/agents/stub-agent.md"
        self.assertTrue(dst.exists())
        self.assertIn("Stub body", dst.read_text())

    def test_copy_hook_is_executable(self):
        install.copy_artifact(
            self.manifest.artifacts["stub-hook"],
            FIXTURES,
            self.target,
            on_conflict=lambda dst: "overwrite",
        )
        dst = self.target / ".claude/hooks/stub-hook.sh"
        self.assertTrue(dst.exists())
        self.assertTrue(dst.stat().st_mode & 0o111)  # any execute bit set

    def test_skip_on_conflict(self):
        dst = self.target / ".claude/agents/stub-agent.md"
        dst.parent.mkdir(parents=True)
        dst.write_text("preexisting content")
        install.copy_artifact(
            self.manifest.artifacts["stub-agent"],
            FIXTURES,
            self.target,
            on_conflict=lambda dst: "skip",
        )
        self.assertEqual(dst.read_text(), "preexisting content")

    def test_overwrite_on_conflict(self):
        dst = self.target / ".claude/agents/stub-agent.md"
        dst.parent.mkdir(parents=True)
        dst.write_text("preexisting content")
        install.copy_artifact(
            self.manifest.artifacts["stub-agent"],
            FIXTURES,
            self.target,
            on_conflict=lambda dst: "overwrite",
        )
        self.assertIn("Stub body", dst.read_text())
```

- [ ] **Step 2: Verify failure**

```bash
python -m unittest tests.test_install -v
```

- [ ] **Step 3: Implement copy logic**

Append to `install.py`:

```python
import shutil
import stat
from typing import Callable


def copy_artifact(
    artifact: dict,
    clank_root: Path,
    target: Path,
    on_conflict: Callable[[Path], str],
) -> bool:
    """Copy an artifact into target/.claude/.

    Returns True if the artifact was copied, False if skipped.
    on_conflict(dst) must return "overwrite", "skip", or "abort".
    Raises InstallError on "abort".
    """
    src = clank_root / artifact["path"]
    dst = _artifact_destination(artifact, target)

    if artifact.get("type") == "skill":
        return _copy_directory(src, dst, on_conflict, is_hook=False)
    copied = _copy_file(src, dst, on_conflict)
    if copied and artifact.get("type") == "hook":
        st = dst.stat()
        dst.chmod(st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return copied


def _artifact_destination(artifact: dict, target: Path) -> Path:
    """Compute where an artifact lands under target/.claude/."""
    src_path = Path(artifact["path"])
    parts = src_path.parts
    if parts[0] == "base":
        rel = Path(*parts[1:])
    elif parts[0] == "addons":
        rel = Path(*parts[2:])
    else:
        raise InstallError(f"artifact path must start with base/ or addons/: {src_path}")
    return target / ".claude" / rel


def _copy_file(src: Path, dst: Path, on_conflict: Callable[[Path], str]) -> bool:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        action = on_conflict(dst)
        if action == "skip":
            return False
        if action == "abort":
            raise InstallError(f"install aborted at {dst}")
        if action != "overwrite":
            raise InstallError(f"unknown conflict action: {action}")
    shutil.copy2(src, dst)
    return True


def _copy_directory(
    src_dir: Path,
    dst_dir: Path,
    on_conflict: Callable[[Path], str],
    is_hook: bool,
) -> bool:
    any_copied = False
    for src_file in sorted(src_dir.rglob("*")):
        if not src_file.is_file():
            continue
        rel = src_file.relative_to(src_dir)
        dst_file = dst_dir / rel
        if _copy_file(src_file, dst_file, on_conflict):
            any_copied = True
    return any_copied
```

- [ ] **Step 4: Verify tests pass**

```bash
python -m unittest tests.test_install -v
```

- [ ] **Step 5: Commit**

```bash
git add install.py tests/test_install.py
git commit -m "feat(installer): add file/directory copy + conflict hooks

copy_artifact() dispatches to _copy_file or _copy_directory based on
artifact type. Hooks get executable bits set. Conflict resolution is
callback-driven so the interactive prompt can live in a separate concern."
```

---

## Task 1.8: `install.py` — settings.json deep merge

Implement the merge algorithm per the spec: hooks merge by `matcher`, dedupe by `command`; `permissions.allow` set-union.

**Files:**
- Modify: `/Users/yasen.dimitrov.ext/repos/clank/install.py`
- Modify: `/Users/yasen.dimitrov.ext/repos/clank/tests/test_install.py`

- [ ] **Step 1: Write failing tests**

```python
class TestSettingsMerge(unittest.TestCase):
    def test_merge_into_empty(self):
        target = {}
        fragment = {
            "hooks": {
                "PreToolUse": [
                    {"matcher": "Bash", "hooks": [{"type": "command", "command": "/a.sh"}]}
                ]
            }
        }
        result = install.merge_settings(target, fragment)
        self.assertEqual(
            result["hooks"]["PreToolUse"][0]["matcher"], "Bash"
        )
        self.assertEqual(
            result["hooks"]["PreToolUse"][0]["hooks"][0]["command"], "/a.sh"
        )

    def test_merge_append_to_existing_matcher(self):
        target = {
            "hooks": {
                "PreToolUse": [
                    {"matcher": "Bash", "hooks": [{"type": "command", "command": "/existing.sh"}]}
                ]
            }
        }
        fragment = {
            "hooks": {
                "PreToolUse": [
                    {"matcher": "Bash", "hooks": [{"type": "command", "command": "/new.sh"}]}
                ]
            }
        }
        result = install.merge_settings(target, fragment)
        cmds = [h["command"] for h in result["hooks"]["PreToolUse"][0]["hooks"]]
        self.assertEqual(cmds, ["/existing.sh", "/new.sh"])

    def test_merge_dedupes_by_command(self):
        target = {
            "hooks": {
                "PreToolUse": [
                    {"matcher": "Bash", "hooks": [{"type": "command", "command": "/a.sh"}]}
                ]
            }
        }
        fragment = {
            "hooks": {
                "PreToolUse": [
                    {"matcher": "Bash", "hooks": [{"type": "command", "command": "/a.sh"}]}
                ]
            }
        }
        result = install.merge_settings(target, fragment)
        hooks = result["hooks"]["PreToolUse"][0]["hooks"]
        self.assertEqual(len(hooks), 1)

    def test_merge_new_matcher(self):
        target = {
            "hooks": {
                "PreToolUse": [
                    {"matcher": "Bash", "hooks": [{"type": "command", "command": "/a.sh"}]}
                ]
            }
        }
        fragment = {
            "hooks": {
                "PreToolUse": [
                    {"matcher": "Edit|Write", "hooks": [{"type": "command", "command": "/b.sh"}]}
                ]
            }
        }
        result = install.merge_settings(target, fragment)
        self.assertEqual(len(result["hooks"]["PreToolUse"]), 2)

    def test_merge_permissions_allow_union(self):
        target = {"permissions": {"allow": ["Bash(ls:*)"]}}
        fragment = {"permissions": {"allow": ["Bash(git status)", "Bash(ls:*)"]}}
        result = install.merge_settings(target, fragment)
        self.assertEqual(
            sorted(result["permissions"]["allow"]),
            ["Bash(git status)", "Bash(ls:*)"],
        )
```

- [ ] **Step 2: Verify failure**

- [ ] **Step 3: Implement merge**

Append to `install.py`:

```python
import copy


def merge_settings(target: dict, fragment: dict) -> dict:
    """Deep-merge fragment into target. Target wins on scalar conflicts.

    Hook arrays merge by `matcher`; within a matched group, hooks dedupe
    by `command`. permissions.allow and permissions.deny set-union.
    """
    result = copy.deepcopy(target)

    for event, frag_entries in (fragment.get("hooks") or {}).items():
        target_entries = result.setdefault("hooks", {}).setdefault(event, [])
        for frag_entry in frag_entries:
            matcher = frag_entry.get("matcher")
            existing = next(
                (e for e in target_entries if e.get("matcher") == matcher),
                None,
            )
            if existing is None:
                target_entries.append(copy.deepcopy(frag_entry))
                continue
            existing_hooks = existing.setdefault("hooks", [])
            existing_cmds = {h.get("command") for h in existing_hooks}
            for frag_hook in frag_entry.get("hooks", []):
                if frag_hook.get("command") not in existing_cmds:
                    existing_hooks.append(copy.deepcopy(frag_hook))
                    existing_cmds.add(frag_hook.get("command"))

    for perm_key in ("allow", "deny"):
        frag_list = (fragment.get("permissions") or {}).get(perm_key)
        if frag_list is None:
            continue
        target_list = result.setdefault("permissions", {}).setdefault(perm_key, [])
        for item in frag_list:
            if item not in target_list:
                target_list.append(item)

    return result
```

- [ ] **Step 4: Verify tests pass**

- [ ] **Step 5: Commit**

```bash
git add install.py tests/test_install.py
git commit -m "feat(installer): add settings.json deep-merge

merge_settings() merges hook entries by matcher (dedupes by command
string), set-unions permissions.allow/deny, preserves target scalars.
Idempotent on re-run."
```

---

## Task 1.9: `install.py` — install receipt

Add receipt write on install, receipt read for uninstall.

**Files:**
- Modify: `/Users/yasen.dimitrov.ext/repos/clank/install.py`
- Modify: `/Users/yasen.dimitrov.ext/repos/clank/tests/test_install.py`

- [ ] **Step 1: Write failing test**

```python
class TestReceipt(unittest.TestCase):
    def test_write_and_read_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            (target / ".claude").mkdir()
            install.write_receipt(
                target,
                artifacts=["stub-agent", "stub-hook"],
                clank_version="0.1.0",
                clank_commit="abc123",
            )
            receipt = install.read_receipt(target)
            self.assertEqual(
                sorted(receipt["artifacts"]),
                ["stub-agent", "stub-hook"],
            )
            self.assertEqual(receipt["clank_version"], "0.1.0")
            self.assertEqual(receipt["clank_commit"], "abc123")
            self.assertIn("installed_at", receipt)

    def test_read_receipt_missing_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            (target / ".claude").mkdir()
            receipt = install.read_receipt(target)
            self.assertEqual(receipt, {"artifacts": []})
```

- [ ] **Step 2: Verify failure**

- [ ] **Step 3: Implement**

```python
from datetime import datetime, timezone

RECEIPT_NAME = ".clank-installed.json"


def write_receipt(
    target: Path,
    artifacts: list[str],
    clank_version: str,
    clank_commit: str,
) -> None:
    existing = read_receipt(target)
    merged = sorted(set(existing.get("artifacts", [])) | set(artifacts))
    receipt = {
        "clank_version": clank_version,
        "clank_commit": clank_commit,
        "installed_at": datetime.now(timezone.utc).isoformat(),
        "target": str(target.resolve()),
        "artifacts": merged,
    }
    (target / ".claude" / RECEIPT_NAME).write_text(
        json.dumps(receipt, indent=2) + "\n"
    )


def read_receipt(target: Path) -> dict:
    path = target / ".claude" / RECEIPT_NAME
    if not path.exists():
        return {"artifacts": []}
    return json.loads(path.read_text())
```

- [ ] **Step 4: Verify tests pass**

- [ ] **Step 5: Commit**

```bash
git add install.py tests/test_install.py
git commit -m "feat(installer): add install receipt read/write

.clank-installed.json tracks installed artifact IDs, clank version/commit,
install timestamp. Re-running install unions new artifacts with existing
receipt so uninstall stays authoritative."
```

---

## Task 1.10: `install.py` — uninstall

Uninstall removes each listed artifact's files and reverse-merges its settings fragment out of the target's settings.json.

**Files:**
- Modify: `/Users/yasen.dimitrov.ext/repos/clank/install.py`
- Modify: `/Users/yasen.dimitrov.ext/repos/clank/tests/test_install.py`

- [ ] **Step 1: Write failing test**

```python
class TestUninstall(unittest.TestCase):
    def setUp(self):
        self.manifest = install.Manifest.load(FIXTURES / "manifest_valid.toml")
        self.tmp = tempfile.TemporaryDirectory()
        self.target = Path(self.tmp.name)
        (self.target / ".claude").mkdir()
        # Install both stub artifacts
        for aid in ["stub-agent", "stub-hook"]:
            install.copy_artifact(
                self.manifest.artifacts[aid],
                FIXTURES,
                self.target,
                on_conflict=lambda dst: "overwrite",
            )
        # Merge the stub-hook fragment
        frag = json.loads(
            (FIXTURES / "base/settings.fragments/stub-hook.json").read_text()
        )
        target_settings = install.merge_settings({}, frag)
        (self.target / ".claude/settings.json").write_text(
            json.dumps(target_settings, indent=2)
        )
        install.write_receipt(
            self.target, ["stub-agent", "stub-hook"], "0.1.0", "test"
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_uninstall_removes_file(self):
        install.uninstall(
            self.manifest, FIXTURES, self.target, ["stub-agent"]
        )
        self.assertFalse(
            (self.target / ".claude/agents/stub-agent.md").exists()
        )

    def test_uninstall_updates_receipt(self):
        install.uninstall(
            self.manifest, FIXTURES, self.target, ["stub-agent"]
        )
        receipt = install.read_receipt(self.target)
        self.assertEqual(receipt["artifacts"], ["stub-hook"])

    def test_uninstall_strips_settings_fragment(self):
        install.uninstall(
            self.manifest, FIXTURES, self.target, ["stub-hook"]
        )
        settings = json.loads(
            (self.target / ".claude/settings.json").read_text()
        )
        bash_hooks = [
            e for e in settings.get("hooks", {}).get("PreToolUse", [])
            if e.get("matcher") == "Bash"
        ]
        all_cmds = []
        for e in bash_hooks:
            all_cmds.extend(h["command"] for h in e.get("hooks", []))
        self.assertNotIn(
            "$CLAUDE_PROJECT_DIR/.claude/hooks/stub-hook.sh", all_cmds
        )
```

- [ ] **Step 2: Verify failure**

- [ ] **Step 3: Implement**

```python
def uninstall(
    manifest: Manifest,
    clank_root: Path,
    target: Path,
    artifact_ids: list[str],
) -> None:
    """Remove listed artifacts from the target and update the receipt."""
    receipt = read_receipt(target)
    installed = set(receipt.get("artifacts", []))

    for aid in artifact_ids:
        if aid not in manifest.artifacts:
            raise InstallError(f"unknown artifact: {aid}")
        artifact = manifest.artifacts[aid]
        dst = _artifact_destination(artifact, target)

        if artifact.get("type") == "skill":
            if dst.is_dir():
                shutil.rmtree(dst)
        elif dst.exists():
            dst.unlink()

        frag_rel = artifact.get("settings_fragment")
        if frag_rel:
            frag = json.loads((clank_root / frag_rel).read_text())
            _unmerge_settings(target, frag)

        installed.discard(aid)

    # Rewrite receipt
    if installed:
        write_receipt(
            target,
            sorted(installed),
            receipt.get("clank_version", __version__),
            receipt.get("clank_commit", "unknown"),
        )
        # write_receipt unions with existing, so we must overwrite cleanly:
        receipt_path = target / ".claude" / RECEIPT_NAME
        data = json.loads(receipt_path.read_text())
        data["artifacts"] = sorted(installed)
        receipt_path.write_text(json.dumps(data, indent=2) + "\n")
    else:
        receipt_path = target / ".claude" / RECEIPT_NAME
        if receipt_path.exists():
            receipt_path.unlink()


def _unmerge_settings(target: Path, fragment: dict) -> None:
    settings_path = target / ".claude" / "settings.json"
    if not settings_path.exists():
        return
    settings = json.loads(settings_path.read_text())

    for event, frag_entries in (fragment.get("hooks") or {}).items():
        target_entries = settings.get("hooks", {}).get(event, [])
        for frag_entry in frag_entries:
            matcher = frag_entry.get("matcher")
            target_entry = next(
                (e for e in target_entries if e.get("matcher") == matcher),
                None,
            )
            if target_entry is None:
                continue
            frag_cmds = {h.get("command") for h in frag_entry.get("hooks", [])}
            target_entry["hooks"] = [
                h for h in target_entry.get("hooks", [])
                if h.get("command") not in frag_cmds
            ]
            if not target_entry["hooks"]:
                target_entries.remove(target_entry)
        if not target_entries:
            settings["hooks"].pop(event, None)
    if not settings.get("hooks"):
        settings.pop("hooks", None)

    for perm_key in ("allow", "deny"):
        frag_list = (fragment.get("permissions") or {}).get(perm_key, [])
        target_list = settings.get("permissions", {}).get(perm_key, [])
        settings.setdefault("permissions", {})[perm_key] = [
            x for x in target_list if x not in frag_list
        ]
        if not settings["permissions"][perm_key]:
            settings["permissions"].pop(perm_key)
    if settings.get("permissions") == {}:
        settings.pop("permissions")

    settings_path.write_text(json.dumps(settings, indent=2) + "\n")
```

Note: the `write_receipt` call in `uninstall` is awkward because `write_receipt` unions with existing. The fix below rewrites the receipt file directly after calling `write_receipt`. A cleaner refactor would be to add a `replace=True` flag to `write_receipt`, but that's a minor follow-up.

- [ ] **Step 4: Verify tests pass**

- [ ] **Step 5: Commit**

```bash
git add install.py tests/test_install.py
git commit -m "feat(installer): add uninstall

uninstall() removes files and reverse-merges settings fragments from the
target. Skill directories are recursively removed. Receipt is rewritten
or deleted when empty."
```

---

## Task 1.11: `install.py` — end-to-end `install()` + `main()` wiring

Wire all the pieces together into a real `install()` flow and make `main()` call it. Two new scenarios cover the full install + merge-over-existing story.

**Files:**
- Modify: `/Users/yasen.dimitrov.ext/repos/clank/install.py`
- Modify: `/Users/yasen.dimitrov.ext/repos/clank/tests/test_install.py`

- [ ] **Step 1: Write failing tests**

```python
class TestFullInstall(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.target = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_install_preset_minimal_clean(self):
        # Use the fixture manifest, not the real one
        install.install(
            manifest_path=FIXTURES / "manifest_valid.toml",
            clank_root=FIXTURES,
            target=self.target,
            preset="minimal",
            include=[],
            exclude=[],
            conflict_policy="overwrite",
            dry_run=False,
            stop_hook_opt_in=False,
            clank_version="test",
            clank_commit="testcommit",
        )
        self.assertTrue((self.target / ".claude/agents/stub-agent.md").exists())
        receipt = install.read_receipt(self.target)
        self.assertEqual(receipt["artifacts"], ["stub-agent"])

    def test_install_over_existing_preserves_unrelated(self):
        (self.target / ".claude").mkdir()
        preexisting = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Read",
                        "hooks": [
                            {"type": "command", "command": "/unrelated.sh"}
                        ],
                    }
                ]
            },
            "permissions": {"allow": ["Bash(echo hi)"]},
            "enabledPlugins": {"existing-plugin": True},
        }
        (self.target / ".claude/settings.json").write_text(
            json.dumps(preexisting, indent=2)
        )

        install.install(
            manifest_path=FIXTURES / "manifest_valid.toml",
            clank_root=FIXTURES,
            target=self.target,
            preset="test-both",
            include=[],
            exclude=[],
            conflict_policy="overwrite",
            dry_run=False,
            stop_hook_opt_in=False,
            clank_version="test",
            clank_commit="testcommit",
        )

        settings = json.loads(
            (self.target / ".claude/settings.json").read_text()
        )
        # Unrelated Read hook preserved
        read_entry = next(
            e for e in settings["hooks"]["PreToolUse"]
            if e["matcher"] == "Read"
        )
        self.assertEqual(
            read_entry["hooks"][0]["command"], "/unrelated.sh"
        )
        # Original permission preserved
        self.assertIn("Bash(echo hi)", settings["permissions"]["allow"])
        # Plugin config preserved
        self.assertEqual(settings["enabledPlugins"]["existing-plugin"], True)
        # New Bash hook from stub-hook fragment added
        bash_entry = next(
            e for e in settings["hooks"]["PreToolUse"]
            if e["matcher"] == "Bash"
        )
        cmds = [h["command"] for h in bash_entry["hooks"]]
        self.assertIn(
            "$CLAUDE_PROJECT_DIR/.claude/hooks/stub-hook.sh", cmds
        )

    def test_install_idempotent(self):
        for _ in range(2):
            install.install(
                manifest_path=FIXTURES / "manifest_valid.toml",
                clank_root=FIXTURES,
                target=self.target,
                preset="test-both",
                include=[],
                exclude=[],
                conflict_policy="overwrite",
                dry_run=False,
                stop_hook_opt_in=False,
                clank_version="test",
                clank_commit="testcommit",
            )
        settings = json.loads(
            (self.target / ".claude/settings.json").read_text()
        )
        bash_entry = next(
            e for e in settings["hooks"]["PreToolUse"]
            if e["matcher"] == "Bash"
        )
        # Same command must not appear twice
        cmds = [h["command"] for h in bash_entry["hooks"]]
        self.assertEqual(len(cmds), len(set(cmds)))
```

- [ ] **Step 2: Verify failure**

- [ ] **Step 3: Implement `install()`**

Append to `install.py`:

```python
def install(
    manifest_path: Path,
    clank_root: Path,
    target: Path,
    preset: str | None,
    include: list[str],
    exclude: list[str],
    conflict_policy: str,
    dry_run: bool,
    stop_hook_opt_in: bool,
    clank_version: str,
    clank_commit: str,
) -> int:
    """Run the full install flow. Returns an exit code."""
    manifest = Manifest.load(manifest_path)
    errors = lint_manifest(manifest, clank_root)
    if errors:
        for e in errors:
            print(f"manifest lint error: {e}", file=sys.stderr)
        return 2

    try:
        selected = resolve_selection(
            manifest, preset=preset, include=include, exclude=exclude
        )
    except ValueError as e:
        print(f"selection error: {e}", file=sys.stderr)
        return 2

    # Apply stop-hook opt-in rule: the hook enters the selection only if
    # the user already listed it via --include OR opted in via the prompt.
    stop_id = "stop-review-reminder"
    if (
        stop_id in manifest.artifacts
        and stop_hook_opt_in
        and manifest.artifacts[stop_id].get("default") is False
    ):
        selected.add(stop_id)

    if not selected:
        print("no artifacts selected", file=sys.stderr)
        return 2

    if not dry_run:
        check_target(target)

    on_conflict = _conflict_callback(conflict_policy)

    copied_ids: list[str] = []
    for aid in sorted(selected):
        artifact = manifest.artifacts[aid]
        src = clank_root / artifact["path"]
        dst = _artifact_destination(artifact, target)
        if dry_run:
            print(f"[dry-run] copy {src} -> {dst}")
            copied_ids.append(aid)
            continue
        copied = copy_artifact(artifact, clank_root, target, on_conflict)
        if copied:
            copied_ids.append(aid)

    # Merge settings fragments for installed hooks
    settings_path = target / ".claude" / "settings.json"
    if not dry_run:
        current = (
            json.loads(settings_path.read_text())
            if settings_path.exists()
            else _seed_settings(clank_root)
        )
        for aid in copied_ids:
            frag_rel = manifest.artifacts[aid].get("settings_fragment")
            if not frag_rel:
                continue
            frag = json.loads((clank_root / frag_rel).read_text())
            current = merge_settings(current, frag)
        settings_path.write_text(json.dumps(current, indent=2) + "\n")

    if not dry_run and copied_ids:
        write_receipt(target, copied_ids, clank_version, clank_commit)

    print(f"installed: {', '.join(copied_ids) if copied_ids else '(nothing)'}")
    return 0


def _conflict_callback(policy: str) -> Callable[[Path], str]:
    if policy == "overwrite":
        return lambda _dst: "overwrite"
    if policy == "skip":
        return lambda _dst: "skip"
    # default interactive policy is wired in main()
    return lambda _dst: "overwrite"


def _seed_settings(clank_root: Path) -> dict:
    base_settings = clank_root / "base" / "settings.json"
    if base_settings.exists():
        return json.loads(base_settings.read_text())
    return {}
```

Then update `main()`:

```python
def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    clank_root = Path(__file__).resolve().parent
    manifest_path = clank_root / "manifest.toml"

    if args.list:
        manifest = Manifest.load(manifest_path)
        for aid, a in sorted(manifest.artifacts.items()):
            tags = ",".join(a.get("tags", []))
            print(f"{aid:30} [{a['type']:10}] ({tags}) — {a.get('description', '')}")
        return 0

    if not args.target:
        parser.error("--target is required unless --list is given")

    if args.uninstall:
        manifest = Manifest.load(manifest_path)
        ids = [x.strip() for x in args.uninstall.split(",") if x.strip()]
        uninstall(manifest, clank_root, args.target, ids)
        print(f"uninstalled: {', '.join(ids)}")
        return 0

    include = [x.strip() for x in (args.include or "").split(",") if x.strip()]
    exclude = [x.strip() for x in (args.exclude or "").split(",") if x.strip()]

    if not args.preset and not include and not args.interactive:
        parser.error("one of --preset, --include, --interactive is required")

    # Stop-hook prompt: always ask once unless --force or already included.
    stop_id = "stop-review-reminder"
    manifest_preview = Manifest.load(manifest_path)
    stop_hook_opt_in = False
    if (
        stop_id in manifest_preview.artifacts
        and stop_id not in include
        and not args.force
        and not args.dry_run
    ):
        answer = input(
            "Include the stop hook that reminds you to run code-reviewer "
            "on code changes? [y/N] "
        ).strip().lower()
        stop_hook_opt_in = answer == "y"

    policy = "overwrite" if args.force else "interactive"
    return install(
        manifest_path=manifest_path,
        clank_root=clank_root,
        target=args.target,
        preset=args.preset,
        include=include,
        exclude=exclude,
        conflict_policy=policy,
        dry_run=args.dry_run,
        stop_hook_opt_in=stop_hook_opt_in,
        clank_version=__version__,
        clank_commit=_git_commit(clank_root),
    )


def _git_commit(clank_root: Path) -> str:
    import subprocess
    try:
        result = subprocess.run(
            ["git", "-C", str(clank_root), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        )
        return result.stdout.strip()[:12]
    except (FileNotFoundError, subprocess.CalledProcessError):
        return "unknown"
```

- [ ] **Step 4: Verify tests pass**

```bash
python -m unittest tests.test_install -v
```

- [ ] **Step 5: Commit**

```bash
git add install.py tests/test_install.py
git commit -m "feat(installer): wire up full install() flow + main()

install() orchestrates manifest lint -> selection resolution -> target
check -> copy -> settings merge -> receipt. main() adds --list, stop-hook
prompt, git-commit detection, and --force vs interactive conflict policy."
```

---

## Task 1.12: `install.py` — interactive picker

Numbered-list picker for `-i/--interactive` mode.

**Files:**
- Modify: `/Users/yasen.dimitrov.ext/repos/clank/install.py`
- Modify: `/Users/yasen.dimitrov.ext/repos/clank/tests/test_install.py`

- [ ] **Step 1: Write failing tests**

```python
import io
from contextlib import redirect_stdout


class TestInteractivePicker(unittest.TestCase):
    def setUp(self):
        self.manifest = install.Manifest.load(FIXTURES / "manifest_valid.toml")

    def test_toggle_and_continue(self):
        user_input = iter(["1", "c", "", "c", "c", "c"])

        def fake_input(_prompt=""):
            return next(user_input)

        selected = install.interactive_pick(
            self.manifest, input_fn=fake_input, output=io.StringIO()
        )
        self.assertIn("stub-agent", selected)

    def test_all_then_none(self):
        user_input = iter(["a", "c", "n", "c", "c", "c"])

        def fake_input(_prompt=""):
            return next(user_input)

        selected = install.interactive_pick(
            self.manifest, input_fn=fake_input, output=io.StringIO()
        )
        self.assertEqual(selected, set())
```

- [ ] **Step 2: Verify failure**

- [ ] **Step 3: Implement**

```python
CATEGORIES = [
    ("agent", "Agents"),
    ("hook", "Hooks"),
    ("rule", "Rules"),
    ("skill", "Skills"),
    ("plugin-doc", "Plugin docs"),
]


def interactive_pick(
    manifest: Manifest,
    input_fn: Callable[[str], str] = input,
    output: "io.TextIOBase | None" = None,
) -> set[str]:
    import sys as _sys
    out = output if output is not None else _sys.stdout
    selected: set[str] = set()

    for artifact_type, heading in CATEGORIES:
        artifacts = sorted(
            (aid for aid, a in manifest.artifacts.items() if a.get("type") == artifact_type)
        )
        if not artifacts:
            continue
        while True:
            print(f"\n== {heading} ==", file=out)
            for i, aid in enumerate(artifacts, 1):
                mark = "x" if aid in selected else " "
                desc = manifest.artifacts[aid].get("description", "")
                print(f"  [{mark}] {i:2}. {aid:30} — {desc}", file=out)
            cmd = input_fn(
                "Toggle (numbers), (a)ll, (n)one, (c)ontinue > "
            ).strip().lower()
            if cmd == "c" or cmd == "":
                break
            if cmd == "a":
                selected |= set(artifacts)
                continue
            if cmd == "n":
                selected -= set(artifacts)
                continue
            for token in cmd.replace(",", " ").split():
                if not token.isdigit():
                    continue
                idx = int(token)
                if 1 <= idx <= len(artifacts):
                    aid = artifacts[idx - 1]
                    if aid in selected:
                        selected.discard(aid)
                    else:
                        selected.add(aid)
    return selected
```

- [ ] **Step 4: Run tests, verify pass**

- [ ] **Step 5: Wire `--interactive` into `main()`**

In `main()`, before the `install()` call, if `args.interactive`:

```python
if args.interactive:
    manifest_for_picker = Manifest.load(manifest_path)
    picked = interactive_pick(manifest_for_picker)
    include = sorted(set(include) | picked)
```

- [ ] **Step 6: Commit**

```bash
git add install.py tests/test_install.py
git commit -m "feat(installer): add numbered-list interactive picker

interactive_pick() walks artifact categories, prints toggleable numbered
lists, accepts numbers + (a)ll + (n)one + (c)ontinue. Pure stdlib
input()/print() — no curses dependency."
```

---

## Task 1.13: `.github/workflows/test.yml`

CI that runs `python -m unittest tests.test_install -v` on push and PR.

**Files:**
- Create: `/Users/yasen.dimitrov.ext/repos/clank/.github/workflows/test.yml`

- [ ] **Step 1: Write the workflow**

```yaml
name: test

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Run installer tests
        run: python -m unittest tests.test_install -v
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/test.yml
git commit -m "ci: run installer tests on push and PR

Uses Python 3.11 and stdlib unittest. No extra dependencies."
```

---

# Phase 2 — Base artifacts

All base content. Each task writes one or more files and ends by appending the artifact entry to `manifest.toml`. Only after all base artifacts are in the manifest does the final Phase 2 task run an end-to-end smoke test against a throwaway target.

Every Phase 2 task references the spec at `docs/superpowers/specs/2026-04-10-clank-template-design.md` — the "base/" contents section spells out exactly what each file must contain. Source material paths:

- **ice-scraper** lifted: `/Users/yasen.dimitrov.ext/repos/ice-scraper/.claude/<path>`
- **affaan-m** lifted: fetched via `gh api repos/affaan-m/everything-claude-code/contents/<path> --jq .content | base64 -d`

---

## Task 2.1: `base/agents/code-reviewer.md`

**Files:**
- Create: `/Users/yasen.dimitrov.ext/repos/clank/base/agents/code-reviewer.md`

**Source:** Lift from `/Users/yasen.dimitrov.ext/repos/ice-scraper/.claude/agents/code-reviewer.md`.

**Changes required (from spec Section `base/agents/`):**
- **Keep**: confidence-based filtering, review dimensions (1, 2, 3, 6, 7, 8), severity mapping, output format, approval criteria, behavioral guidelines, shell safety section
- **Drop**: Section "0. Database Schema Validation" (it's NHL-schema specific)
- **Drop**: Section "4. Python Best Practices" (moves to python addon)
- **Drop**: Section "5. FastAPI Patterns" (moves to python addon)
- **Drop**: DataFrame-specific bullets in Section "1. Correctness & Bug Detection" (moves to python addon)
- **Drop**: Section "9. Project Style & Conventions" (NHL/MoneyPuck specifics)
- **Replace**: `frontmatter` — remove `mcpServers: - postgres` (base agent should not require MCP), keep `model: sonnet`, `tools: Read, Write, Grep, Glob, Bash, Edit`, `memory: project`
- **Edit**: opening paragraph — change "elite Python code reviewer with deep expertise in production-grade data engineering, web backends (FastAPI)…" to "elite software engineering code reviewer with deep expertise across languages and paradigms" (or similar language-agnostic phrasing)

- [ ] **Step 1: Read the source**

```bash
cat /Users/yasen.dimitrov.ext/repos/ice-scraper/.claude/agents/code-reviewer.md
```

- [ ] **Step 2: Write the stripped version**

Write to `base/agents/code-reviewer.md`. Preserve the ice-scraper version's overall section structure, just with the sections listed above removed and the frontmatter/opening edited.

- [ ] **Step 3: Append to manifest**

Add to `manifest.toml` under `artifacts = []` (which becomes a TOML array of tables — remove the `= []` line and write):

```toml
[[artifacts]]
id = "code-reviewer"
type = "agent"
path = "base/agents/code-reviewer.md"
description = "Language-agnostic code reviewer — confidence filtering, severity mapping, AI-code quirks"
tags = ["base", "review"]
```

- [ ] **Step 4: Verify the manifest lints clean**

```bash
cd /Users/yasen.dimitrov.ext/repos/clank
python -c "
import install
from pathlib import Path
m = install.Manifest.load(Path('manifest.toml'))
errors = install.lint_manifest(m, Path('.'))
print('OK' if not errors else 'ERRORS:\n' + '\n'.join(errors))
"
```

Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add base/agents/code-reviewer.md manifest.toml
git commit -m "feat(base): add code-reviewer agent

Lifted from ice-scraper with project-specific sections removed
(schema validation, Python best practices, FastAPI, DataFrame checks,
project conventions). Remains read-only and keeps confidence-based
filtering, review dimensions, severity mapping, output format."
```

---

## Task 2.2: `base/agents/security-reviewer.md`

**Files:**
- Create: `/Users/yasen.dimitrov.ext/repos/clank/base/agents/security-reviewer.md`

**Source:** New. Narrow focus per spec: OWASP Top 10, injection (SQL/command/XSS), hardcoded secrets, eval/exec, unsafe deserialization, weak crypto, path traversal, auth/authz bypass, secrets in logs.

Frontmatter:
```markdown
---
name: security-reviewer
description: "Security-focused code reviewer. Use PROACTIVELY on any code change touching authentication, authorization, user input handling, cryptography, deserialization, file paths, SQL, shell commands, or external API calls. Also use before commits involving the above areas."
model: sonnet
tools: Read, Grep, Glob, Bash
memory: project
---
```

Body must cover (each as its own section):
1. OWASP Top 10 quick scan
2. Injection vectors (SQL, command, XSS, LDAP, header injection)
3. Secrets & credentials (hardcoded, leaked via logs, weak env var handling)
4. Cryptography (weak algorithms, ECB mode, hardcoded keys, MD5/SHA1 for security use)
5. Deserialization (pickle, yaml unsafe load, marshal on untrusted input)
6. Path traversal (unsanitized file paths, `..` not rejected)
7. Authn/authz (missing checks, IDOR, session fixation)
8. Unsafe eval/exec (on user input)
9. Output format: same `Critical / High / Medium / Low` + verdict structure as `code-reviewer.md` for consistency

Read-only agent; same "never write anything" clause as code-reviewer.

- [ ] **Step 1: Write the file**

Draft the agent per the structure above. Keep it under ~200 lines.

- [ ] **Step 2: Append to manifest**

```toml
[[artifacts]]
id = "security-reviewer"
type = "agent"
path = "base/agents/security-reviewer.md"
description = "OWASP-focused security reviewer — injection, secrets, crypto, deserialization, path traversal"
tags = ["base", "review", "security"]
```

- [ ] **Step 3: Lint check**

```bash
python -c "import install; from pathlib import Path; m=install.Manifest.load(Path('manifest.toml')); e=install.lint_manifest(m, Path('.')); print('OK' if not e else e)"
```

- [ ] **Step 4: Commit**

```bash
git add base/agents/security-reviewer.md manifest.toml
git commit -m "feat(base): add security-reviewer agent

New agent focused on OWASP Top 10 categories. Read-only; same output
format as code-reviewer for consistency."
```

---

## Task 2.3: `base/agents/database-reviewer.md`

**Files:**
- Create: `/Users/yasen.dimitrov.ext/repos/clank/base/agents/database-reviewer.md`

**Source:** Lift from `/Users/yasen.dimitrov.ext/repos/ice-scraper/.claude/agents/db-integrity-auditor.md`.

**Changes required:**
- **Keep**: Phases 1-6 (Schema Validation, Data Completeness, Uniqueness, Referential Integrity, Accuracy/Format, Operational Health), the "read-only auditor" safety clause, the memory-path discipline
- **Drop**: "Critical Project Context" (NHL jobs schedule, ice-scraper table list)
- **Drop**: "Known Gotchas" (game_id float, date/time ET/UTC specific to ice-scraper, `_migration_log` reference, signal lifecycle)
- **Drop**: Phase 5b (Opening/Closing Odds — entirely ice-scraper)
- **Edit**: agent name `db-integrity-auditor` → `database-reviewer`
- **Edit**: opening expertise paragraph — make Postgres-generic (drop "ice-scraper" mentions)
- **Edit**: frontmatter `description` — generalize the examples to not mention "odds scraper" or "signals table". Use generic phrasings: "The scrape_foo job…", "The fact table…"
- **Keep**: frontmatter `mcpServers: [postgres]`, `memory: project`

- [ ] **Step 1: Read the source**

```bash
wc -l /Users/yasen.dimitrov.ext/repos/ice-scraper/.claude/agents/db-integrity-auditor.md
```

Expected: ~500 lines. Read it and identify the sections to strip.

- [ ] **Step 2: Write the stripped version**

- [ ] **Step 3: Append to manifest**

```toml
[[artifacts]]
id = "database-reviewer"
type = "agent"
path = "base/agents/database-reviewer.md"
description = "Postgres database integrity auditor — schema drift, gaps, duplicates, FK integrity, operational health"
tags = ["base", "review", "postgres"]
requires_mcp = ["postgres"]
```

- [ ] **Step 4: Lint check**

- [ ] **Step 5: Commit**

```bash
git add base/agents/database-reviewer.md manifest.toml
git commit -m "feat(base): add database-reviewer agent

Lifted from ice-scraper's db-integrity-auditor with Critical Project
Context and Known Gotchas removed. Generic Postgres integrity auditor —
Phases 1-6 (schema validation through operational health) retained."
```

---

## Task 2.4: `base/agents/docs-researcher.md`

**Files:**
- Create: `/Users/yasen.dimitrov.ext/repos/clank/base/agents/docs-researcher.md`

**Source:** New. Purpose: fetch current library/framework docs, protecting main context window from large doc dumps. Uses `ctx7` CLI as primary (per the user's global rule), WebFetch as fallback.

Frontmatter:
```markdown
---
name: docs-researcher
description: "Fetches up-to-date documentation for libraries, frameworks, SDKs, CLIs, and cloud services. Use when the user asks about a specific technology's API, configuration, CLI usage, version migration, setup instructions, or library-specific debugging — even for well-known technologies — because training data may be stale. Use instead of WebSearch for library docs."
model: sonnet
tools: Bash, WebFetch, Read
---
```

Body covers:
- The `ctx7` CLI workflow (resolve library ID → fetch docs): `npx ctx7@latest library <name> "<question>"` then `npx ctx7@latest docs <id> "<question>"`
- How to pick the best match from library resolution results
- Version-pinned docs: `/org/project/version` syntax
- WebFetch fallback only if ctx7 fails or returns no results
- No more than 3 commands per question
- Do not include API keys/credentials in queries

- [ ] **Step 1: Write the file**

- [ ] **Step 2: Append to manifest**

```toml
[[artifacts]]
id = "docs-researcher"
type = "agent"
path = "base/agents/docs-researcher.md"
description = "Documentation fetcher — uses ctx7 CLI then WebFetch. Protects main context from doc dumps."
tags = ["base", "research"]
```

- [ ] **Step 3: Lint check**

- [ ] **Step 4: Commit**

---

## Task 2.5: `base/agents/doc-updater.md`

**Files:**
- Create: `/Users/yasen.dimitrov.ext/repos/clank/base/agents/doc-updater.md`

**Source:** New. Reviews recent code changes against existing project docs and reports stale sections without writing.

Frontmatter:
```markdown
---
name: doc-updater
description: "Reviews recent code changes against existing project documentation (README, CLAUDE.md, API references, in-repo guides) and reports which sections are now stale. Use after significant feature work, API changes, or config changes. Read-only — reports, does not write."
model: sonnet
tools: Read, Grep, Glob, Bash
memory: project
---
```

Body covers:
- What it checks: README feature lists, CLAUDE.md project-structure sections, API references, command-line help text, config file docs, in-code docstrings vs. signatures
- Workflow: diff recent changes → grep docs for relevant keywords → flag mismatches
- Output format: numbered list of (file:section, what's stale, suggested update as 1-2 sentences)
- Must not write

- [ ] **Step 1: Write the file**

- [ ] **Step 2: Append to manifest**

```toml
[[artifacts]]
id = "doc-updater"
type = "agent"
path = "base/agents/doc-updater.md"
description = "Reports stale sections in project docs relative to recent code changes. Read-only."
tags = ["base", "docs"]
```

- [ ] **Step 3: Lint check**

- [ ] **Step 4: Commit**

---

## Task 2.6: `base/hooks/pretooluse-bash-safety.sh` + fragment

**Files:**
- Create: `/Users/yasen.dimitrov.ext/repos/clank/base/hooks/pretooluse-bash-safety.sh`
- Create: `/Users/yasen.dimitrov.ext/repos/clank/base/settings.fragments/bash-safety.json`

**Source:** Lift from `/Users/yasen.dimitrov.ext/repos/ice-scraper/.claude/hooks/pretooluse-bash-checks.sh`.

**Keep:**
- Shebang, jq availability check, input sanitization
- Pre-push reminder (exit 1 — warn)
- Destructive SQL block (DROP/TRUNCATE/DELETE FROM — exit 2)
- UPDATE statement block with generic error message (no ice-scraper /tmp/<name>.py mention)
- `rm` block
- tmux reminder for long-running commands (keep generic form: npm, yarn, pnpm, cargo, pytest)

**Drop:**
- biome `--unsafe` block (too project-specific)
- ALTER/INSERT warn (move to sql addon)
- scp-to-VPS warn (ice-scraper only)
- pip vs uv warn (move to python addon)
- Parallel model training warn (ice-scraper only)
- FeatureCache/seed_moneypuck/backfill/sync_moneypuck warns (ice-scraper only)
- backtest/seed/backfill/feature/discovery/sync/generate_signals warns (ice-scraper only)

**Fragment `bash-safety.json`:**
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

- [ ] **Step 1: Write the hook script (stripped)**

Start from ice-scraper's version, delete listed sections, keep error messages generic.

- [ ] **Step 2: Make it executable**

```bash
chmod +x /Users/yasen.dimitrov.ext/repos/clank/base/hooks/pretooluse-bash-safety.sh
```

- [ ] **Step 3: Write the fragment JSON**

- [ ] **Step 4: Append to manifest**

```toml
[[artifacts]]
id = "bash-safety"
type = "hook"
path = "base/hooks/pretooluse-bash-safety.sh"
settings_fragment = "base/settings.fragments/bash-safety.json"
description = "PreToolUse Bash guardrails — git push reminder, destructive SQL block, rm block, tmux reminder"
tags = ["base", "safety"]
```

- [ ] **Step 5: Lint check**

- [ ] **Step 6: Smoke-test the hook**

```bash
echo '{"tool_input":{"command":"git push origin main"}}' | \
  /Users/yasen.dimitrov.ext/repos/clank/base/hooks/pretooluse-bash-safety.sh; echo "exit: $?"
```

Expected: warning about pre-push + exit code 1.

```bash
echo '{"tool_input":{"command":"rm -rf /"}}' | \
  /Users/yasen.dimitrov.ext/repos/clank/base/hooks/pretooluse-bash-safety.sh; echo "exit: $?"
```

Expected: BLOCKED message + exit code 2.

- [ ] **Step 7: Commit**

```bash
git add base/hooks/pretooluse-bash-safety.sh base/settings.fragments/bash-safety.json manifest.toml
git commit -m "feat(base): add pretooluse-bash-safety hook

Lifted from ice-scraper's pretooluse-bash-checks.sh with project-specific
warnings removed (biome unsafe, scp VPS, pip vs uv, model/feature scripts).
Keeps: git-push reminder, destructive SQL block, rm block, long-running
tmux reminder."
```

---

## Task 2.7: `base/hooks/pretooluse-file-safety.sh` + fragment

**Files:**
- Create: `/Users/yasen.dimitrov.ext/repos/clank/base/hooks/pretooluse-file-safety.sh`
- Create: `/Users/yasen.dimitrov.ext/repos/clank/base/settings.fragments/file-safety.json`

**Source:** Generalize from ice-scraper's `pretooluse-file-checks.sh` (which hardcodes `schema.py`).

**Required behavior:**
- Read JSON stdin, extract `tool_input.file_path` and `tool_input.new_string` / `tool_input.content`
- Config block at top: `FILE_PATTERNS` (regex, default: `'(schema|migration|migrations|\.sql)'`), `FORBIDDEN_PATTERNS` (regex, default: `'(DROP[[:space:]]+TABLE|DROP[[:space:]]+COLUMN|TRUNCATE|DELETE[[:space:]]+FROM)'`)
- If file matches `FILE_PATTERNS` AND content matches `FORBIDDEN_PATTERNS` → exit 2 with descriptive block message
- Otherwise exit 0

Header comment must say: "Edit the config block at the top to customize which files trigger which pattern blocks for this project."

**Fragment:**
```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/pretooluse-file-safety.sh",
            "statusMessage": "File safety checks..."
          }
        ]
      }
    ]
  }
}
```

- [ ] **Step 1: Write the script**

- [ ] **Step 2: `chmod +x`**

- [ ] **Step 3: Write the fragment**

- [ ] **Step 4: Append to manifest**

```toml
[[artifacts]]
id = "file-safety"
type = "hook"
path = "base/hooks/pretooluse-file-safety.sh"
settings_fragment = "base/settings.fragments/file-safety.json"
description = "PreToolUse Edit|Write guardrails — blocks destructive DDL in matching files"
tags = ["base", "safety"]
```

- [ ] **Step 5: Smoke-test**

```bash
echo '{"tool_input":{"file_path":"db/schema.sql","new_string":"DROP TABLE users;"}}' | \
  /Users/yasen.dimitrov.ext/repos/clank/base/hooks/pretooluse-file-safety.sh; echo "exit: $?"
```

Expected: BLOCKED message + exit 2.

```bash
echo '{"tool_input":{"file_path":"src/app.py","new_string":"print(\"hello\")"}}' | \
  /Users/yasen.dimitrov.ext/repos/clank/base/hooks/pretooluse-file-safety.sh; echo "exit: $?"
```

Expected: exit 0 (no block).

- [ ] **Step 6: Commit**

---

## Task 2.8: `base/hooks/stop-review-reminder.sh` + fragment

**Files:**
- Create: `/Users/yasen.dimitrov.ext/repos/clank/base/hooks/stop-review-reminder.sh`
- Create: `/Users/yasen.dimitrov.ext/repos/clank/base/settings.fragments/stop-review-reminder.json`

**Source:** Lift from `/Users/yasen.dimitrov.ext/repos/ice-scraper/.claude/hooks/stop-checks.sh`.

**Changes:**
- Parameterize the file-extension filter at the top of the script as `EXTENSIONS=".py .ts .tsx .js .jsx .go .rs .svelte .sh .sql"`, then build the grep regex from it
- Keep the 120-second marker file pattern (prevents infinite loop)
- Reminder text: "Code changes detected. Before completing: (1) Run the code-reviewer agent and fix all should-fix findings. (2) If available, run /simplify on changed code. If already done, you may proceed."
- Header comment explaining this hook is opt-in via the installer prompt

**Fragment:**
```json
{
  "hooks": {
    "Stop": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/stop-review-reminder.sh"
          }
        ]
      }
    ]
  }
}
```

- [ ] **Step 1: Write the script**

- [ ] **Step 2: `chmod +x`**

- [ ] **Step 3: Write the fragment**

- [ ] **Step 4: Append to manifest (with default = false)**

```toml
[[artifacts]]
id = "stop-review-reminder"
type = "hook"
path = "base/hooks/stop-review-reminder.sh"
settings_fragment = "base/settings.fragments/stop-review-reminder.json"
description = "Stop hook that reminds you to run code-reviewer on code changes. Installer prompts once before enabling."
tags = ["base", "review"]
default = false
```

- [ ] **Step 5: Lint check**

- [ ] **Step 6: Commit**

---

## Task 2.9: `base/rules/` — all 9 rules in one commit

Writing 9 rule files in one commit because each is small (30-100 lines) and they don't depend on each other. TDD doesn't apply — they're content, not code.

**Files:**
- Create: `/Users/yasen.dimitrov.ext/repos/clank/base/rules/code-review.md`
- Create: `/Users/yasen.dimitrov.ext/repos/clank/base/rules/long-running-scripts.md`
- Create: `/Users/yasen.dimitrov.ext/repos/clank/base/rules/no-inline-comments.md`
- Create: `/Users/yasen.dimitrov.ext/repos/clank/base/rules/update-agent-memory.md`
- Create: `/Users/yasen.dimitrov.ext/repos/clank/base/rules/use-project-code-reviewer.md`
- Create: `/Users/yasen.dimitrov.ext/repos/clank/base/rules/executing-actions-with-care.md`
- Create: `/Users/yasen.dimitrov.ext/repos/clank/base/rules/agents.md`
- Create: `/Users/yasen.dimitrov.ext/repos/clank/base/rules/testing.md`
- Create: `/Users/yasen.dimitrov.ext/repos/clank/base/rules/coding-style.md`

- [ ] **Step 1: Lift `code-review.md`**

Source: `/Users/yasen.dimitrov.ext/repos/ice-scraper/.claude/rules/code-review.md`. Lift verbatim, then delete the "Python loops over DataFrames - vectorize instead" bullet under Performance.

- [ ] **Step 2: Lift `long-running-scripts.md`**

Source: `/Users/yasen.dimitrov.ext/repos/ice-scraper/.claude/rules/long-running-scripts.md`. Lift verbatim — 100% generic already.

- [ ] **Step 3: Lift `no-inline-comments.md`**

Source: `/Users/yasen.dimitrov.ext/repos/ice-scraper/.claude/rules/no-inline-comments.md`. Lift verbatim.

- [ ] **Step 4: Lift `update-agent-memory.md`**

Source: `/Users/yasen.dimitrov.ext/repos/ice-scraper/.claude/rules/update-agent-memory.md`. Lift and replace the `db-integrity-auditor` example with a generic reference: "e.g., after fixing issues surfaced by any agent that maintains an audit baseline or memory state".

- [ ] **Step 5: Lift `use-project-code-reviewer.md`**

Source: `/Users/yasen.dimitrov.ext/repos/ice-scraper/.claude/rules/use-project-code-reviewer.md`. Drop ice-scraper-specific mentions (schema validation, DataFrame, FastAPI, NHL API). Generalize: the project's own `code-reviewer` agent knows the project's conventions, language addons, and domain rules better than any generic reviewer.

- [ ] **Step 6: Write new `executing-actions-with-care.md`**

Distill the "Executing actions with care" doctrine from Claude Code's default system prompt into a project rule. Sections:
- Reversibility & blast radius (local/reversible vs. hard-to-reverse vs. shared-state)
- Examples of risky actions warranting confirmation (destructive operations, force push, CI/CD changes, external messages)
- Investigate unexpected state before overwriting
- Scope discipline: authorization stands for the scope specified

~60 lines.

- [ ] **Step 7: Write new `agents.md`**

Modeled on affaan-m's `rules/common/agents.md`. Structure:
- "Available Agents" table listing clank's base agents: code-reviewer, security-reviewer, database-reviewer, docs-researcher, doc-updater (plus a note about language reviewers added by addons)
- "Immediate Agent Usage" section (when to use without user prompt): after code written → code-reviewer; auth/crypto change → security-reviewer; DB integrity concern → database-reviewer; new library question → docs-researcher; after feature work → doc-updater
- "Parallel Task Execution" — use parallel agent dispatch for independent operations
- "Multi-Perspective Analysis" — split role subagents for complex problems

Fetch the affaan-m source for reference and adapt:
```bash
gh api repos/affaan-m/everything-claude-code/contents/rules/common/agents.md --jq '.content' | base64 -d
```

- [ ] **Step 8: Lift `testing.md`**

Source: affaan-m's `rules/common/testing.md`.

```bash
gh api repos/affaan-m/everything-claude-code/contents/rules/common/testing.md --jq '.content' | base64 -d
```

Changes: drop the `tdd-guide` agent reference (clank doesn't ship that agent — the `test-driven-development` skill from superpowers covers TDD discipline instead). Change "Troubleshooting Test Failures" step 1 from "Use tdd-guide agent" to "Consult superpowers:test-driven-development skill".

- [ ] **Step 9: Lift `coding-style.md`**

Source: affaan-m's `rules/common/coding-style.md`.

```bash
gh api repos/affaan-m/everything-claude-code/contents/rules/common/coding-style.md --jq '.content' | base64 -d
```

Lift verbatim. The affaan-m version is already language-agnostic.

- [ ] **Step 10: Append 9 entries to manifest.toml**

```toml
[[artifacts]]
id = "code-review"
type = "rule"
path = "base/rules/code-review.md"
description = "When and how to conduct code review"
tags = ["base", "review", "process"]

[[artifacts]]
id = "long-running-scripts"
type = "rule"
path = "base/rules/long-running-scripts.md"
description = "Smoke-test and optimize before running long scripts"
tags = ["base", "process"]

[[artifacts]]
id = "no-inline-comments"
type = "rule"
path = "base/rules/no-inline-comments.md"
description = "Avoid comments inside python -c multiline strings (bash security heuristic)"
tags = ["base", "safety"]

[[artifacts]]
id = "update-agent-memory"
type = "rule"
path = "base/rules/update-agent-memory.md"
description = "Update agent memory after resolving issues they surfaced"
tags = ["base", "process"]

[[artifacts]]
id = "use-project-code-reviewer"
type = "rule"
path = "base/rules/use-project-code-reviewer.md"
description = "Prefer the project's own code-reviewer agent over generic reviewers"
tags = ["base", "review"]

[[artifacts]]
id = "executing-actions-with-care"
type = "rule"
path = "base/rules/executing-actions-with-care.md"
description = "Reversibility, blast radius, and confirmation discipline for risky actions"
tags = ["base", "safety"]

[[artifacts]]
id = "agents"
type = "rule"
path = "base/rules/agents.md"
description = "Index of available agents and when to delegate"
tags = ["base", "agents"]

[[artifacts]]
id = "testing"
type = "rule"
path = "base/rules/testing.md"
description = "TDD workflow, AAA pattern, descriptive test names"
tags = ["base", "testing"]

[[artifacts]]
id = "coding-style"
type = "rule"
path = "base/rules/coding-style.md"
description = "KISS/DRY/YAGNI, file organization, naming, immutability"
tags = ["base", "style"]
```

- [ ] **Step 11: Lint check**

- [ ] **Step 12: Commit**

```bash
git add base/rules/ manifest.toml
git commit -m "feat(base): add 9 base rules

code-review, long-running-scripts, no-inline-comments, update-agent-memory,
use-project-code-reviewer (all lifted from ice-scraper, generalized),
executing-actions-with-care (new), agents/testing/coding-style (lifted
from affaan-m/everything-claude-code with minor edits)."
```

---

## Task 2.10: `base/skills/review/`

**Files:**
- Create: `/Users/yasen.dimitrov.ext/repos/clank/base/skills/review/SKILL.md`

**Source:** New. A `/review` user-invokable skill that dispatches the `code-reviewer` agent on recent changes, plus `security-reviewer` in parallel if the diff touches auth/crypto/input handling.

Frontmatter:
```markdown
---
name: review
description: "Run code review on recently modified code. Invoke via /review."
disable-model-invocation: true
---
```

Body describes the workflow:
1. `git diff` to identify recent changes
2. Launch `code-reviewer` agent in background on the diff
3. Scan diff for keywords suggesting security scope: `auth`, `crypto`, `hash`, `password`, `token`, `secret`, `sql`, `subprocess`, `shell`, `eval`, `exec`, `pickle`, `yaml.load`
4. If any matched, launch `security-reviewer` agent in parallel
5. When both return, consolidate findings by severity
6. Present to user

- [ ] **Step 1: Write `SKILL.md`**

- [ ] **Step 2: Append to manifest (path is directory)**

```toml
[[artifacts]]
id = "review"
type = "skill"
path = "base/skills/review"
description = "/review — runs code-reviewer (+ security-reviewer if relevant) on recent changes"
tags = ["base", "review"]
```

- [ ] **Step 3: Lint check**

- [ ] **Step 4: Commit**

---

## Task 2.11: `base/skills/smoke-test/`

**Files:**
- Create: `/Users/yasen.dimitrov.ext/repos/clank/base/skills/smoke-test/SKILL.md`

**Source:** New. A `/smoke-test` skill that walks through the long-running-scripts pre-flight checklist before running an expensive command.

Frontmatter:
```markdown
---
name: smoke-test
description: "Pre-flight checklist for long-running scripts. Invoke via /smoke-test."
disable-model-invocation: true
---
```

Body: step-by-step walk through imports, DB connection, dependencies, memory check (against the script's estimated usage vs. `free -m`), a tiny-subset dry run. Ends by asking the user for approval before proceeding to the full run.

- [ ] **Step 1: Write `SKILL.md`**

- [ ] **Step 2: Append to manifest**

```toml
[[artifacts]]
id = "smoke-test"
type = "skill"
path = "base/skills/smoke-test"
description = "/smoke-test — pre-flight checklist before running expensive scripts"
tags = ["base", "process"]
```

- [ ] **Step 3: Lint + commit**

---

## Task 2.12: `base/skills/deploy/` (scaffold)

**Files:**
- Create: `/Users/yasen.dimitrov.ext/repos/clank/base/skills/deploy/SKILL.md`

**Source:** Lift from `/Users/yasen.dimitrov.ext/repos/ice-scraper/.claude/skills/deploy/SKILL.md` and genericize into a scaffold.

Frontmatter:
```markdown
---
name: deploy
description: "Deploy the current branch to production. Scaffold — edit this file to add your deploy command. Invoke via /deploy."
disable-model-invocation: true
---
```

Body keeps the structure:
1. Pre-flight checks (clean branch, pushed to origin, CI green) — generic
2. Deploy command — `# TODO: fill in your project's deploy command here (e.g., ssh server "cd /app && git pull && systemctl restart svc")`
3. Post-deploy verification — `# TODO: fill in your service health check`
4. Rollback — keep generic "show the error, identify last good commit, do not roll back automatically"

- [ ] **Step 1: Write `SKILL.md`**

- [ ] **Step 2: Append to manifest**

```toml
[[artifacts]]
id = "deploy"
type = "skill"
path = "base/skills/deploy"
description = "/deploy — scaffold skill for deployment (user fills in project-specific commands)"
tags = ["base", "deploy"]
```

- [ ] **Step 3: Lint + commit**

---

## Task 2.13: `base/plugins/plugins.md`

**Files:**
- Create: `/Users/yasen.dimitrov.ext/repos/clank/base/plugins/plugins.md`

**Source:** Distill from affaan-m's `plugins/README.md`. Keep the lists and install commands; drop the marketplace discussion beyond the bare minimum.

```bash
gh api repos/affaan-m/everything-claude-code/contents/plugins/README.md --jq '.content' | base64 -d
```

Add a clank-specific opening sentence explaining this is a reference list of plugins the user typically installs across projects.

Include: the `claude plugin marketplace add` + `claude plugin install` commands, then tables for:
- Development: typescript-lsp, pyright-lsp, hookify, code-simplifier
- Code Quality: code-review, pr-review-toolkit, security-guidance
- Search: mgrep, context7
- Workflow: commit-commands, frontend-design, feature-dev
- MCP servers: postgres (for database-reviewer + sql addon), context7 (for docs-researcher)

- [ ] **Step 1: Write the file**

- [ ] **Step 2: Append to manifest**

```toml
[[artifacts]]
id = "plugins-doc"
type = "plugin-doc"
path = "base/plugins/plugins.md"
description = "Reference list of Claude Code plugins typically installed"
tags = ["base", "docs"]
```

- [ ] **Step 3: Lint + commit**

---

## Task 2.14: `base/settings.json`

**Files:**
- Create: `/Users/yasen.dimitrov.ext/repos/clank/base/settings.json`

**Content:** Reference wiring that only includes `bash-safety` + `file-safety`. `stop-review-reminder` is NOT included here — it's only added via the installer prompt + fragment merge.

```json
{
  "permissions": {
    "allow": []
  },
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
      },
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/pretooluse-file-safety.sh",
            "statusMessage": "File safety checks..."
          }
        ]
      }
    ]
  }
}
```

- [ ] **Step 1: Write the file**

- [ ] **Step 2: Append to manifest (as a "plugin-doc" style reference — or NOT at all; the installer reads it from `base/settings.json` directly to seed new targets)**

Actually, `base/settings.json` is not a manifest artifact — it's a seed file the installer reads in `_seed_settings()` when the target has no existing settings.json. Do NOT add to manifest. Do add a comment in `manifest.toml` or `install.md` pointing at this file.

- [ ] **Step 3: Verify the installer's `_seed_settings()` can find it (run tests again)**

```bash
python -m unittest tests.test_install -v
```

Expected: all tests still pass.

- [ ] **Step 4: Commit**

```bash
git add base/settings.json
git commit -m "feat(base): add reference settings.json

Seed file the installer reads via _seed_settings() when a target has no
existing .claude/settings.json. Contains only base-tagged PreToolUse
entries (bash-safety, file-safety). Stop hook is opt-in via installer
prompt and not wired here."
```

---

## Task 2.15: End-to-end smoke test — install `base-only` preset

After all base artifacts are in place and the manifest has them all, add the `base-only` preset to `manifest.toml`, then run the installer against a throwaway target and verify everything lands correctly.

**Files:**
- Modify: `/Users/yasen.dimitrov.ext/repos/clank/manifest.toml`

- [ ] **Step 1: Add presets to manifest**

Replace the empty `[presets]` block with:

```toml
[presets]
minimal = ["bash-safety", "file-safety", "code-reviewer", "executing-actions-with-care"]
base-only = ["@tag:base"]
```

- [ ] **Step 2: Lint the manifest**

```bash
cd /Users/yasen.dimitrov.ext/repos/clank
python -c "import install; from pathlib import Path; m=install.Manifest.load(Path('manifest.toml')); e=install.lint_manifest(m, Path('.')); print('OK' if not e else '\n'.join(e))"
```

Expected: OK.

- [ ] **Step 3: Install base-only into a throwaway target**

```bash
TARGET=$(mktemp -d)
echo "Target: $TARGET"
cd /Users/yasen.dimitrov.ext/repos/clank
python install.py --target "$TARGET" --preset base-only --force
```

Expected: output lists every base artifact, exit 0.

- [ ] **Step 4: Inspect the target**

```bash
find "$TARGET/.claude" -type f | sort
cat "$TARGET/.claude/.clank-installed.json"
cat "$TARGET/.claude/settings.json" | python -m json.tool
```

Expected:
- All 5 agents under `.claude/agents/`
- 2 hooks under `.claude/hooks/` with executable bits set
- 9 rules under `.claude/rules/`
- 3 skill directories under `.claude/skills/` with their SKILL.md files
- `.claude/plugins/plugins.md`
- `.claude/settings.json` with both PreToolUse matchers present
- `.clank-installed.json` listing every base artifact ID

- [ ] **Step 5: Run uninstall on a couple artifacts and verify clean removal**

```bash
python install.py --target "$TARGET" --uninstall doc-updater,docs-researcher
ls "$TARGET/.claude/agents/" | grep -E "(doc-updater|docs-researcher)" && echo "STILL THERE - FAIL" || echo "removed OK"
cat "$TARGET/.claude/.clank-installed.json" | python -c "import json,sys; d=json.load(sys.stdin); assert 'doc-updater' not in d['artifacts']; assert 'docs-researcher' not in d['artifacts']; print('receipt OK')"
```

- [ ] **Step 6: Clean up and commit**

```bash
rm -rf "$TARGET"
git add manifest.toml
git commit -m "feat(base): add minimal + base-only presets, verify end-to-end install

Added base-only (@tag:base expansion) and minimal presets. Ran
./install.py --target /tmp/... --preset base-only --force against a
throwaway target — all files land correctly, settings.json seeded with
base hooks, uninstall round-trip works."
```

---

# Phase 3 — Addons

Each addon follows the same pattern: write artifacts → update manifest → smoke test via `./install.py --preset <addon>`. The python addon is the most content-heavy because it lifts ~150 lines of Python-specific review from the ice-scraper code-reviewer.

---

## Task 3.1: `addons/python/` — all artifacts

**Files:**
- Create: `/Users/yasen.dimitrov.ext/repos/clank/addons/python/agents/python-reviewer.md`
- Create: `/Users/yasen.dimitrov.ext/repos/clank/addons/python/hooks/ruff-check.sh`
- Create: `/Users/yasen.dimitrov.ext/repos/clank/addons/python/settings.fragments/ruff.json`
- Create: `/Users/yasen.dimitrov.ext/repos/clank/addons/python/rules/python-coding-style.md`
- Create: `/Users/yasen.dimitrov.ext/repos/clank/addons/python/rules/python-testing.md`
- Create: `/Users/yasen.dimitrov.ext/repos/clank/addons/python/rules/python-security.md`
- Create: `/Users/yasen.dimitrov.ext/repos/clank/addons/python/rules/python-patterns.md`

- [ ] **Step 1: Write `python-reviewer.md`**

Lift from `/Users/yasen.dimitrov.ext/repos/ice-scraper/.claude/agents/code-reviewer.md` — **keep** the sections that were dropped from the base reviewer:
- "4. Python Best Practices" (mutable default args, pathlib over os.path, isinstance, Enum, etc.)
- "5. FastAPI Patterns" (no blocking in async, Pydantic validation, response_model, LIMIT on user-facing queries)
- DataFrame join integrity bullets (generalized: "after any `.merge()`, `.loc[]`, or join, verify there is a row count assertion — silent empty joins are a top-10 cause of data pipeline bugs")
- Python-specific performance bullets (no iterrows, vectorize, etc.)

Update frontmatter:
```markdown
---
name: python-reviewer
description: "Expert Python code reviewer. Use PROACTIVELY when reviewing Python code — FastAPI endpoints, async code, DataFrame pipelines, or any Python file. Use alongside the base code-reviewer for language-specific depth."
model: sonnet
tools: Read, Grep, Glob, Bash, Edit
memory: project
---
```

Drop ice-scraper-specific conventions (NHL API URL, MoneyPuck quirks, odds decimal, uv vs pip — uv-only is fine to keep as "prefer uv if available").

- [ ] **Step 2: Write `ruff-check.sh` (path-flexible)**

```bash
#!/bin/bash
# PostToolUse hook: run ruff on edited Python files
# Returns decision:block with errors if ruff fails so Claude fixes them.
#
# Searches for ruff in: ./venv/bin/ruff, ./.venv/bin/ruff, uv run ruff, $PATH.
# Bails silently if none are available.

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_response.filePath // empty')

if [[ ! "$FILE_PATH" =~ \.py$ ]]; then
  exit 0
fi

if [[ ! -f "$FILE_PATH" ]]; then
  exit 0
fi

PROJECT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"

# Resolve a ruff binary
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
  exit 0
fi

ERRORS=""
if ! LINT_OUTPUT=$($RUFF check "$FILE_PATH" 2>&1); then
  ERRORS="$LINT_OUTPUT"
fi
if ! FMT_OUTPUT=$($RUFF format --check "$FILE_PATH" 2>&1); then
  ERRORS="${ERRORS:+$ERRORS\n}$FMT_OUTPUT"
fi

if [[ -n "$ERRORS" ]]; then
  jq -n --arg errors "$ERRORS" '{
    decision: "block",
    reason: ("ruff found issues:\n" + $errors + "\nPlease fix these issues.")
  }'
fi
exit 0
```

`chmod +x` it.

- [ ] **Step 3: Write `settings.fragments/ruff.json`**

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

- [ ] **Step 4: Lift 4 python rules from affaan-m**

Fetch each via `gh api repos/affaan-m/everything-claude-code/contents/rules/python/<topic>.md --jq .content | base64 -d`. Files are:

- `python-coding-style.md`
- `python-testing.md`
- `python-security.md`
- `python-patterns.md`

Write each verbatim into `addons/python/rules/`. If the affaan-m path doesn't exist, adapt from `rules/common/<topic>.md` with Python-specific additions.

Check what's available first:
```bash
gh api 'repos/affaan-m/everything-claude-code/git/trees/main?recursive=1' --jq '.tree[] | select(.path | test("rules/python")) | .path'
```

If the repo only has `.cursor/rules/python-*.md` (which is what I saw earlier), lift from there — same content, different path.

- [ ] **Step 5: Append 7 entries to `manifest.toml`**

```toml
[[artifacts]]
id = "python-reviewer"
type = "agent"
path = "addons/python/agents/python-reviewer.md"
description = "Python specialist reviewer — FastAPI, DataFrame, async, pytest"
tags = ["python", "review"]

[[artifacts]]
id = "ruff"
type = "hook"
path = "addons/python/hooks/ruff-check.sh"
settings_fragment = "addons/python/settings.fragments/ruff.json"
description = "PostToolUse ruff check on edited Python files"
tags = ["python", "lint"]

[[artifacts]]
id = "python-coding-style"
type = "rule"
path = "addons/python/rules/python-coding-style.md"
description = "Python-specific coding style (naming, typing, pathlib, comprehensions)"
tags = ["python", "style"]

[[artifacts]]
id = "python-testing"
type = "rule"
path = "addons/python/rules/python-testing.md"
description = "Python testing patterns — pytest, fixtures, parametrize"
tags = ["python", "testing"]

[[artifacts]]
id = "python-security"
type = "rule"
path = "addons/python/rules/python-security.md"
description = "Python security — eval/exec, pickle, yaml.load, subprocess shell=True"
tags = ["python", "security"]

[[artifacts]]
id = "python-patterns"
type = "rule"
path = "addons/python/rules/python-patterns.md"
description = "Python idioms — context managers, dataclasses, Enum, generators"
tags = ["python", "patterns"]
```

- [ ] **Step 6: Add the `python` preset**

```toml
python = ["@preset:base-only", "python-reviewer", "ruff", "python-coding-style", "python-testing", "python-security", "python-patterns"]
```

- [ ] **Step 7: Lint manifest**

- [ ] **Step 8: Smoke-test install**

```bash
TARGET=$(mktemp -d)
cd /Users/yasen.dimitrov.ext/repos/clank
python install.py --target "$TARGET" --preset python --force
find "$TARGET/.claude" -type f | sort
cat "$TARGET/.claude/settings.json" | python -m json.tool
rm -rf "$TARGET"
```

Expected: base artifacts + python-reviewer + ruff-check.sh + 4 python rules. `settings.json` has ruff wired in `PostToolUse[Edit|Write]`.

- [ ] **Step 9: Smoke-test the ruff hook with a bad file**

```bash
cat > /tmp/bad.py <<'EOF'
import os, sys
x=1
EOF
echo "{\"tool_input\":{\"file_path\":\"/tmp/bad.py\"}}" | \
  /Users/yasen.dimitrov.ext/repos/clank/addons/python/hooks/ruff-check.sh
rm /tmp/bad.py
```

Expected: either ruff-blocks with errors (if ruff is installed) or silent exit 0 (if not). Both are valid — the hook must not crash.

- [ ] **Step 10: Commit**

```bash
git add addons/python/ manifest.toml
git commit -m "feat(addons/python): add python-reviewer, ruff hook, 4 rules, fragment, preset

Lifted python-reviewer from ice-scraper's code-reviewer (the sections
removed in Task 2.1). Path-flexible ruff-check hook searches venv/.venv/
uv run/PATH. 4 python rules lifted from affaan-m/everything-claude-code.
New 'python' preset composes base-only + python artifacts."
```

---

## Task 3.2: `addons/typescript/`

**Files:**
- Create: `/Users/yasen.dimitrov.ext/repos/clank/addons/typescript/agents/typescript-reviewer.md`
- Create: `/Users/yasen.dimitrov.ext/repos/clank/addons/typescript/hooks/biome-check.sh`
- Create: `/Users/yasen.dimitrov.ext/repos/clank/addons/typescript/hooks/svelte-check.sh`
- Create: `/Users/yasen.dimitrov.ext/repos/clank/addons/typescript/settings.fragments/biome.json`
- Create: `/Users/yasen.dimitrov.ext/repos/clank/addons/typescript/settings.fragments/svelte-check.json`
- Create: `/Users/yasen.dimitrov.ext/repos/clank/addons/typescript/rules/typescript-coding-style.md`
- Create: `/Users/yasen.dimitrov.ext/repos/clank/addons/typescript/rules/typescript-testing.md`
- Create: `/Users/yasen.dimitrov.ext/repos/clank/addons/typescript/rules/typescript-security.md`
- Create: `/Users/yasen.dimitrov.ext/repos/clank/addons/typescript/rules/typescript-patterns.md`

- [ ] **Step 1: Write `typescript-reviewer.md`** (new, ~150 lines)

TS/JS specialist covering: strict types + no `any`, promise/async patterns, React hooks rules, import/export hygiene, Next.js server-vs-client component patterns, React key prop discipline, `useEffect` pitfalls, `Object.hasOwn` vs `.hasOwnProperty`, `for…of` over `forEach` when breaking is possible, Node.js ESM vs CJS, JSX accessibility basics.

Frontmatter:
```markdown
---
name: typescript-reviewer
description: "Expert TypeScript/JavaScript code reviewer. Use PROACTIVELY when reviewing .ts, .tsx, .js, .jsx, .svelte, or .vue files. Deep coverage: strict types, React hooks, promise handling, Next.js patterns, ESM/CJS."
model: sonnet
tools: Read, Grep, Glob, Bash, Edit
memory: project
---
```

- [ ] **Step 2: Lift + de-hardcode `biome-check.sh`**

Start from `/Users/yasen.dimitrov.ext/repos/ice-scraper/.claude/hooks/biome-check.sh`. Changes:
- Search order for biome binary: `./node_modules/.bin/biome` → `./frontend/node_modules/.bin/biome` → `biome` on PATH
- Drop the `frontend/src/` path filter (fire on any matching file under the project)
- Bail silently if biome not found

- [ ] **Step 3: Lift + generalize `svelte-check.sh`**

From ice-scraper. Only fires on `*.svelte` files. Bails silently if `svelte-check` not installed. Header comment: "Included in the typescript addon because Svelte is a TS project with extra tooling. Safe to leave installed on non-Svelte projects — the hook is inert on non-.svelte files."

- [ ] **Step 4: `chmod +x` both hooks**

- [ ] **Step 5: Write both fragments**

`biome.json`:
```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/biome-check.sh",
            "statusMessage": "Running biome..."
          }
        ]
      }
    ]
  }
}
```

`svelte-check.json`:
```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/svelte-check.sh",
            "statusMessage": "Running svelte-check..."
          }
        ]
      }
    ]
  }
}
```

- [ ] **Step 6: Lift 4 typescript rules from affaan-m**

Same process as Task 3.1 Step 4 — fetch from `.cursor/rules/typescript-*.md`, write verbatim.

- [ ] **Step 7: Append 9 entries to manifest + typescript preset**

```toml
[[artifacts]]
id = "typescript-reviewer"
type = "agent"
path = "addons/typescript/agents/typescript-reviewer.md"
description = "TypeScript/JavaScript specialist reviewer — types, hooks, promises, Next.js, ESM"
tags = ["typescript", "javascript", "review"]

[[artifacts]]
id = "biome"
type = "hook"
path = "addons/typescript/hooks/biome-check.sh"
settings_fragment = "addons/typescript/settings.fragments/biome.json"
description = "PostToolUse biome check on edited TS/JS/Svelte files"
tags = ["typescript", "lint"]

[[artifacts]]
id = "svelte-check"
type = "hook"
path = "addons/typescript/hooks/svelte-check.sh"
settings_fragment = "addons/typescript/settings.fragments/svelte-check.json"
description = "PostToolUse svelte-check on .svelte files. Inert on non-Svelte projects."
tags = ["typescript", "svelte", "lint"]

[[artifacts]]
id = "typescript-coding-style"
type = "rule"
path = "addons/typescript/rules/typescript-coding-style.md"
description = "TypeScript-specific coding style"
tags = ["typescript", "style"]

[[artifacts]]
id = "typescript-testing"
type = "rule"
path = "addons/typescript/rules/typescript-testing.md"
description = "TypeScript testing patterns — vitest, jest, RTL"
tags = ["typescript", "testing"]

[[artifacts]]
id = "typescript-security"
type = "rule"
path = "addons/typescript/rules/typescript-security.md"
description = "TypeScript security — XSS, prototype pollution, eval, innerHTML"
tags = ["typescript", "security"]

[[artifacts]]
id = "typescript-patterns"
type = "rule"
path = "addons/typescript/rules/typescript-patterns.md"
description = "TypeScript idioms — discriminated unions, branded types, exhaustive switches"
tags = ["typescript", "patterns"]
```

Preset:
```toml
typescript = ["@preset:base-only", "typescript-reviewer", "biome", "svelte-check", "typescript-coding-style", "typescript-testing", "typescript-security", "typescript-patterns"]
```

- [ ] **Step 8: Lint + smoke test**

```bash
TARGET=$(mktemp -d)
python install.py --target "$TARGET" --preset typescript --force
find "$TARGET/.claude" -type f | sort
rm -rf "$TARGET"
```

- [ ] **Step 9: Commit**

```bash
git add addons/typescript/ manifest.toml
git commit -m "feat(addons/typescript): add ts/js specialist + biome, svelte-check, 4 rules

New typescript-reviewer agent (strict types, hooks, promises, Next.js).
Path-flexible biome-check and svelte-check hooks lifted from ice-scraper
with hardcoded paths removed. 4 typescript rules from affaan-m. New
'typescript' preset."
```

---

## Task 3.3: `addons/sql/`

**Files:**
- Create: `/Users/yasen.dimitrov.ext/repos/clank/addons/sql/agents/sql-reviewer.md`
- Create: `/Users/yasen.dimitrov.ext/repos/clank/addons/sql/hooks/pretooluse-mcp-postgres-safety.sh`
- Create: `/Users/yasen.dimitrov.ext/repos/clank/addons/sql/settings.fragments/mcp-postgres-safety.json`
- Create: `/Users/yasen.dimitrov.ext/repos/clank/addons/sql/rules/sql-safety.md`
- Create: `/Users/yasen.dimitrov.ext/repos/clank/addons/sql/skills/querying-db/SKILL.md`
- Create: `/Users/yasen.dimitrov.ext/repos/clank/addons/sql/skills/querying-db/schema.txt.template`
- Create: `/Users/yasen.dimitrov.ext/repos/clank/addons/sql/skills/migration/SKILL.md`

- [ ] **Step 1: Write `sql-reviewer.md`**

New agent, distinct from base `database-reviewer` (which audits DB health). This one reviews queries for: parameterization (SQL injection), N+1 patterns, missing indexes (via hypothesis + EXPLAIN suggestion), window function clarity, `SELECT *` discipline, CTE vs subquery readability, transaction scope.

Frontmatter:
```markdown
---
name: sql-reviewer
description: "SQL query reviewer. Use when reviewing any code that contains SQL (raw strings, ORM calls, migrations). Focuses on correctness and performance of individual queries — not database health (use database-reviewer for that)."
model: sonnet
tools: Read, Grep, Glob, Bash
memory: project
---
```

- [ ] **Step 2: Lift `pretooluse-mcp-postgres-safety.sh`**

From `/Users/yasen.dimitrov.ext/repos/ice-scraper/.claude/hooks/pretooluse-mcp-postgres-checks.sh`. Already ~95% generic. Only change: drop the `/tmp/<name>.py` and `.venv/bin/python` ice-scraper idiom from the UPDATE block's error message. Replace with generic: "Write the mutation logic to a script the user can review, and run it yourself after approval. Do NOT run UPDATE directly via the MCP tool."

`chmod +x`.

- [ ] **Step 3: Write `mcp-postgres-safety.json`**

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "mcp__postgres__query",
        "hooks": [
          {
            "type": "command",
            "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/pretooluse-mcp-postgres-safety.sh",
            "statusMessage": "SQL safety checks..."
          }
        ]
      }
    ]
  }
}
```

- [ ] **Step 4: Write `sql-safety.md` rule**

New rule. Sections:
- Destructive DDL requires explicit user approval
- All DDL must be idempotent (`IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`)
- Parameterized queries only — never string-concat user input
- Read-only by default — INSERT/UPDATE/DELETE require approval
- Transaction discipline — begin/commit explicit, never leave transactions open
- Migrations run at deploy time only, never from scheduled jobs

- [ ] **Step 5: Lift `querying-db/SKILL.md`**

From `/Users/yasen.dimitrov.ext/repos/ice-scraper/.claude/skills/querying-db/SKILL.md`. Strip ice-scraper specifics (MoneyPuck camelCase, game_id float, ET vs UTC, ice-scraper SSH tunnel). Keep the generic workflow:

1. Read `<project>/.claude/skills/querying-db/schema.txt` before writing any query
2. Use `mcp__postgres__query` if the postgres MCP is configured
3. Fallback: find the project's database helper (via `rg 'get_connection'` or similar) and use it

Frontmatter:
```markdown
---
name: querying-db
description: Use when running SQL queries, database lookups, or Python scripts that touch a SQL database — enforces reading the schema reference first, using the postgres MCP when available, and avoiding common pitfalls.
---
```

- [ ] **Step 6: Write `querying-db/schema.txt.template`**

A scaffold showing the format. Header comment: "This is a template. Rename to schema.txt and fill in your project's schema here." Include example table entries showing the format:

```
## Tables

### users
- id                   BIGINT          PRIMARY KEY
- email                TEXT            NOT NULL, UNIQUE
- created_at           TIMESTAMPTZ     NOT NULL DEFAULT now()
- role                 users_role      NOT NULL DEFAULT 'member'
# notes: users_role enum = ('admin', 'member', 'viewer')

### orders
- id                   BIGINT          PRIMARY KEY
- user_id              BIGINT          NOT NULL REFERENCES users(id)
- amount_cents         INTEGER         NOT NULL CHECK (amount_cents >= 0)
- created_at           TIMESTAMPTZ     NOT NULL DEFAULT now()
- status               TEXT            NOT NULL DEFAULT 'pending'
# notes: status is one of ('pending', 'paid', 'refunded', 'cancelled')

## Enums

### users_role
admin | member | viewer

## Common joins

- orders → users: orders.user_id = users.id
```

- [ ] **Step 7: Lift + generalize `migration/SKILL.md`**

From `/Users/yasen.dimitrov.ext/repos/ice-scraper/.claude/skills/migration/SKILL.md`. Keep safety rules (no DROP/TRUNCATE/unbounded DELETE, idempotent DDL, migrations at deploy time only, lock_timeout discipline). Replace the Python-specific `MIGRATIONS` list + `schema.py` workflow with a generic "Your migration system" section the user fills in: "Edit this file to describe your project's migration approach — whether that's Alembic, Django migrations, raw SQL files, golang-migrate, or a Python MIGRATIONS list."

Frontmatter:
```markdown
---
name: migration
description: Create a new database migration. Scaffold — edit the 'Your migration system' section after install to describe your project's specific workflow. Invoke via /migration.
disable-model-invocation: true
---
```

- [ ] **Step 8: Append 6 entries + sql preset to manifest**

```toml
[[artifacts]]
id = "sql-reviewer"
type = "agent"
path = "addons/sql/agents/sql-reviewer.md"
description = "SQL query reviewer — parameterization, N+1, indexes, CTE clarity"
tags = ["sql", "review"]

[[artifacts]]
id = "mcp-postgres-safety"
type = "hook"
path = "addons/sql/hooks/pretooluse-mcp-postgres-safety.sh"
settings_fragment = "addons/sql/settings.fragments/mcp-postgres-safety.json"
description = "PreToolUse guardrail on mcp__postgres__query — blocks DROP/TRUNCATE/DELETE/UPDATE"
tags = ["sql", "safety", "postgres"]

[[artifacts]]
id = "sql-safety"
type = "rule"
path = "addons/sql/rules/sql-safety.md"
description = "SQL safety — destructive DDL discipline, parameterized queries, migration rules"
tags = ["sql", "safety"]

[[artifacts]]
id = "querying-db"
type = "skill"
path = "addons/sql/skills/querying-db"
description = "Read schema.txt then query via postgres MCP. Ships with schema.txt.template scaffold."
tags = ["sql", "postgres"]

[[artifacts]]
id = "migration"
type = "skill"
path = "addons/sql/skills/migration"
description = "/migration — scaffold for creating idempotent DB migrations (user fills in their toolchain)"
tags = ["sql", "database"]
```

Preset:
```toml
sql = ["@preset:base-only", "sql-reviewer", "mcp-postgres-safety", "sql-safety", "querying-db", "migration"]
```

- [ ] **Step 9: Lint + smoke test**

```bash
TARGET=$(mktemp -d)
python install.py --target "$TARGET" --preset sql --force
find "$TARGET/.claude" -type f | sort
cat "$TARGET/.claude/settings.json" | python -m json.tool
rm -rf "$TARGET"
```

- [ ] **Step 10: Commit**

```bash
git add addons/sql/ manifest.toml
git commit -m "feat(addons/sql): add sql-reviewer, mcp-postgres safety hook, 2 skills, 1 rule

sql-reviewer reviews individual queries (parameterization, N+1, indexes,
CTEs) — distinct from base database-reviewer which audits DB health.
pretooluse-mcp-postgres-safety lifted from ice-scraper with ice-scraper
idioms removed. querying-db skill + schema.txt.template scaffold.
migration skill is a scaffold for user's toolchain."
```

---

## Task 3.4: `addons/go/`

**Files:**
- Create: `/Users/yasen.dimitrov.ext/repos/clank/addons/go/agents/go-reviewer.md`
- Create: `/Users/yasen.dimitrov.ext/repos/clank/addons/go/hooks/golangci-lint-check.sh`
- Create: `/Users/yasen.dimitrov.ext/repos/clank/addons/go/settings.fragments/golangci-lint.json`
- Create: `/Users/yasen.dimitrov.ext/repos/clank/addons/go/rules/golang-coding-style.md`
- Create: `/Users/yasen.dimitrov.ext/repos/clank/addons/go/rules/golang-testing.md`
- Create: `/Users/yasen.dimitrov.ext/repos/clank/addons/go/rules/golang-security.md`
- Create: `/Users/yasen.dimitrov.ext/repos/clank/addons/go/rules/golang-patterns.md`

- [ ] **Step 1: Write `go-reviewer.md`**

New. Go specialist: error wrapping (`fmt.Errorf("...: %w", err)`), `context.Context` propagation (first parameter, never stored in structs), goroutine leak patterns (always provide a way to stop), channel direction (`<-chan` vs `chan<-`), `sync.Mutex` vs `sync.RWMutex`, nil interface vs nil pointer gotcha, proper `defer` placement (not in loops for heavy resources), package naming (lowercase, no underscores), interface at consumer not producer, `errors.Is`/`errors.As` over `==`.

- [ ] **Step 2: Write `golangci-lint-check.sh`**

```bash
#!/bin/bash
# PostToolUse hook: run golangci-lint on edited Go files
# Bails silently if golangci-lint isn't installed or the project isn't a Go module.

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_response.filePath // empty')

if [[ ! "$FILE_PATH" =~ \.go$ ]]; then
  exit 0
fi
if [[ ! -f "$FILE_PATH" ]]; then
  exit 0
fi

PROJECT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"

if [[ ! -f "$PROJECT_DIR/go.mod" ]]; then
  exit 0
fi
if ! command -v golangci-lint >/dev/null 2>&1; then
  exit 0
fi

PKG_DIR="$(dirname "$FILE_PATH")"

if LINT_OUTPUT=$(cd "$PROJECT_DIR" && golangci-lint run "$PKG_DIR/..." 2>&1); then
  exit 0
else
  jq -n --arg errors "$LINT_OUTPUT" '{
    decision: "block",
    reason: ("golangci-lint found issues:\n" + $errors + "\nPlease fix these issues.")
  }'
fi
exit 0
```

`chmod +x`.

- [ ] **Step 3: Write fragment**

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/golangci-lint-check.sh",
            "statusMessage": "Running golangci-lint..."
          }
        ]
      }
    ]
  }
}
```

- [ ] **Step 4: Lift 4 golang rules from affaan-m**

Same fetch pattern as Python. Path: `.cursor/rules/golang-*.md`.

- [ ] **Step 5: Append 6 manifest entries + go preset**

```toml
[[artifacts]]
id = "go-reviewer"
type = "agent"
path = "addons/go/agents/go-reviewer.md"
description = "Go specialist reviewer — error wrapping, context, goroutine leaks, channel safety"
tags = ["go", "review"]

[[artifacts]]
id = "golangci-lint"
type = "hook"
path = "addons/go/hooks/golangci-lint-check.sh"
settings_fragment = "addons/go/settings.fragments/golangci-lint.json"
description = "PostToolUse golangci-lint on edited Go files"
tags = ["go", "lint"]

[[artifacts]]
id = "golang-coding-style"
type = "rule"
path = "addons/go/rules/golang-coding-style.md"
description = "Go coding style — naming, package layout, errors"
tags = ["go", "style"]

[[artifacts]]
id = "golang-testing"
type = "rule"
path = "addons/go/rules/golang-testing.md"
description = "Go testing — table-driven tests, t.Parallel, golden files"
tags = ["go", "testing"]

[[artifacts]]
id = "golang-security"
type = "rule"
path = "addons/go/rules/golang-security.md"
description = "Go security — crypto/rand, sql injection, goroutine leaks"
tags = ["go", "security"]

[[artifacts]]
id = "golang-patterns"
type = "rule"
path = "addons/go/rules/golang-patterns.md"
description = "Go idioms — small interfaces, functional options, sync.Once"
tags = ["go", "patterns"]
```

Preset:
```toml
go = ["@preset:base-only", "go-reviewer", "golangci-lint", "golang-coding-style", "golang-testing", "golang-security", "golang-patterns"]
```

- [ ] **Step 6: Lint + smoke test + commit**

Same as previous addon tasks.

---

## Task 3.5: `addons/rust/`

**Files:**
- Create: `/Users/yasen.dimitrov.ext/repos/clank/addons/rust/agents/rust-reviewer.md`
- Create: `/Users/yasen.dimitrov.ext/repos/clank/addons/rust/hooks/cargo-clippy-check.sh`
- Create: `/Users/yasen.dimitrov.ext/repos/clank/addons/rust/settings.fragments/cargo-clippy.json`
- Create: `/Users/yasen.dimitrov.ext/repos/clank/addons/rust/rules/rust-coding-style.md`
- Create: `/Users/yasen.dimitrov.ext/repos/clank/addons/rust/rules/rust-testing.md`
- Create: `/Users/yasen.dimitrov.ext/repos/clank/addons/rust/rules/rust-security.md`

All content is new — affaan-m has no Rust rules.

- [ ] **Step 1: Write `rust-reviewer.md`**

Ownership/borrow hints, lifetime elision vs explicit, `unsafe` scrutiny (with required safety comments), `Result`/`Option` with `?`, avoiding `.unwrap()` and `.expect()` outside tests, trait bounds simplicity, `async`/`tokio` patterns (no `.block_on()` in async code), `Arc<Mutex<T>>` vs channels, cargo workspace idioms, clippy lint discipline.

- [ ] **Step 2: Write `cargo-clippy-check.sh`**

```bash
#!/bin/bash
# PostToolUse hook: run cargo clippy on edited Rust files
# Bails silently if not a Cargo workspace.

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_response.filePath // empty')

if [[ ! "$FILE_PATH" =~ \.rs$ ]]; then
  exit 0
fi
if [[ ! -f "$FILE_PATH" ]]; then
  exit 0
fi

PROJECT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"

if [[ ! -f "$PROJECT_DIR/Cargo.toml" ]]; then
  exit 0
fi
if ! command -v cargo >/dev/null 2>&1; then
  exit 0
fi

if CLIPPY_OUTPUT=$(cd "$PROJECT_DIR" && cargo clippy --workspace --all-targets --quiet -- -D warnings 2>&1); then
  exit 0
else
  jq -n --arg errors "$CLIPPY_OUTPUT" '{
    decision: "block",
    reason: ("cargo clippy found issues:\n" + $errors + "\nPlease fix these issues.")
  }'
fi
exit 0
```

- [ ] **Step 3: Write fragment**

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/cargo-clippy-check.sh",
            "statusMessage": "Running cargo clippy..."
          }
        ]
      }
    ]
  }
}
```

- [ ] **Step 4: Write 3 Rust rules**

- `rust-coding-style.md`: naming conventions (snake_case fns, PascalCase types, SCREAMING_CASE constants), module organization, `mod.rs` vs named files, prelude use, doc comments (`///` for items, `//!` for crates), formatting via `cargo fmt`.
- `rust-testing.md`: `#[test]` and `#[cfg(test)] mod tests`, property testing (proptest/quickcheck), benchmark discipline, doctest usage, integration tests in `tests/`.
- `rust-security.md`: avoid `unsafe` without documented invariants, `cargo audit` on dependencies, careful with `mem::transmute`, bounds checks.

- [ ] **Step 5: Append manifest entries + rust preset**

```toml
[[artifacts]]
id = "rust-reviewer"
type = "agent"
path = "addons/rust/agents/rust-reviewer.md"
description = "Rust specialist reviewer — ownership, lifetimes, Result/Option, unsafe scrutiny, clippy"
tags = ["rust", "review"]

[[artifacts]]
id = "cargo-clippy"
type = "hook"
path = "addons/rust/hooks/cargo-clippy-check.sh"
settings_fragment = "addons/rust/settings.fragments/cargo-clippy.json"
description = "PostToolUse cargo clippy on edited Rust files"
tags = ["rust", "lint"]

[[artifacts]]
id = "rust-coding-style"
type = "rule"
path = "addons/rust/rules/rust-coding-style.md"
description = "Rust coding style — naming, modules, doc comments"
tags = ["rust", "style"]

[[artifacts]]
id = "rust-testing"
type = "rule"
path = "addons/rust/rules/rust-testing.md"
description = "Rust testing — unit, integration, property, doctests"
tags = ["rust", "testing"]

[[artifacts]]
id = "rust-security"
type = "rule"
path = "addons/rust/rules/rust-security.md"
description = "Rust security — unsafe discipline, cargo audit, bounds checks"
tags = ["rust", "security"]
```

Preset:
```toml
rust = ["@preset:base-only", "rust-reviewer", "cargo-clippy", "rust-coding-style", "rust-testing", "rust-security"]
```

- [ ] **Step 6: Lint + smoke test + commit**

---

## Task 3.6: Composite presets + `all` preset

Wire the remaining presets from the spec:

- [ ] **Step 1: Add to manifest**

```toml
python-sql = ["@preset:python", "@preset:sql"]
typescript-sql = ["@preset:typescript", "@preset:sql"]
fullstack-python = ["@preset:python", "@preset:typescript", "@preset:sql"]
all = ["@tag:*"]
```

- [ ] **Step 2: Lint**

- [ ] **Step 3: Smoke-test each composite**

```bash
for preset in python-sql typescript-sql fullstack-python all; do
  TARGET=$(mktemp -d)
  echo "=== $preset ==="
  python install.py --target "$TARGET" --preset "$preset" --force > /dev/null
  echo "Files: $(find "$TARGET/.claude" -type f | wc -l)"
  rm -rf "$TARGET"
done
```

Expected: every preset installs cleanly.

- [ ] **Step 4: Commit**

```bash
git add manifest.toml
git commit -m "feat(manifest): add composite presets + all preset

python-sql, typescript-sql, fullstack-python, all. Verified every preset
installs cleanly against a throwaway target."
```

---

# Phase 4 — Docs + wrap-up

---

## Task 4.1: `docs/install.md`

Full installer CLI reference. Content:
- Python 3.11+ requirement
- Every flag with description + example
- Install sequence walkthrough
- Conflict handling UX + `--force` behavior
- Receipt format
- Uninstall workflow
- Safety guarantees
- FAQ: "what if I already have a `.claude/settings.json`?", "how do I uninstall everything?", "can I re-run the installer safely?"

- [ ] **Step 1: Write `docs/install.md`**

- [ ] **Step 2: Commit**

---

## Task 4.2: `docs/authoring-agents.md`

How to add a new agent to clank.
- Frontmatter fields (name, description, tools, model, memory, mcpServers)
- The `description` field is a router signal (the main Claude matches it against user intent), not human documentation — write it as "use when…"
- Read-only agent convention (never Write, never shell Write ops)
- Memory path discipline (project memory under `.claude/agent-memory/<agent-name>/`)
- Output format consistency (use same severity/verdict structure as code-reviewer where possible)
- Checklist before adding to manifest

- [ ] **Step 1: Write**
- [ ] **Step 2: Commit**

---

## Task 4.3: `docs/authoring-hooks.md`

- Hook lifecycle: PreToolUse, PostToolUse, Stop, UserPromptSubmit
- Exit code semantics: 0 pass, 1 warn (stderr shown to user, tool proceeds), 2 block (stderr shown to model, tool prevented)
- JSON stdin → JSON decision output pattern (for Stop hooks)
- Path-flexible tool detection pattern (with the ruff/biome search-order example)
- Bailing silently when tools not installed
- Testing hooks via `echo '{...}' | ./hook.sh; echo $?`
- How to add a fragment + manifest entry

- [ ] **Step 1: Write**
- [ ] **Step 2: Commit**

---

## Task 4.4: `docs/authoring-skills.md`

- Skill frontmatter (name, description)
- `disable-model-invocation: true` for user-invokable `/skill` style
- Skill directories and supporting files
- When to use a skill vs. a rule
- Example: how `deploy` ships as a scaffold

- [ ] **Step 1: Write**
- [ ] **Step 2: Commit**

---

## Task 4.5: `docs/authoring-rules.md`

- What rules are: markdown files auto-loaded as project instructions
- Why they inject into every conversation — be mindful of size
- When NOT to use a rule (large reference docs → use `plugins/` or `docs/` instead)
- Good rule characteristics: focused, under 200 lines, one topic per file

- [ ] **Step 1: Write**
- [ ] **Step 2: Commit**

---

## Task 4.6: `docs/adding-an-addon.md`

Walkthrough of adding a new language addon, using `addons/python/` as the worked example.
- Create `addons/<lang>/{agents,hooks,rules,skills,settings.fragments}/`
- Write artifacts
- Make hooks executable
- Write fragments
- Append manifest entries
- Add preset
- Lint check
- Smoke test install
- Update `base/rules/agents.md` if the new addon ships a reviewer

- [ ] **Step 1: Write**
- [ ] **Step 2: Commit**

---

## Task 4.7: Rewrite `README.md`

**Files:**
- Modify: `/Users/yasen.dimitrov.ext/repos/clank/README.md` (currently one line)

Sections:
1. **What clank is** — one paragraph
2. **Quickstart** — `git clone`, `./install.py --target ~/repos/new-project --preset python-sql`
3. **Requirements** — Python 3.11+, git, bash, optional language tools (ruff, biome, golangci-lint, cargo, svelte-check)
4. **Presets** — table of preset name + members
5. **Individual artifacts** — `./install.py --list`
6. **Conflict handling** — short summary, link to `docs/install.md`
7. **Uninstall** — example
8. **Extending** — link to `docs/adding-an-addon.md`
9. **Credits** — ice-scraper internals, affaan-m/everything-claude-code

- [ ] **Step 1: Write**

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: rewrite README with quickstart + presets + usage"
```

---

## Task 4.8: Expand `CLAUDE.md`

**Files:**
- Modify: `/Users/yasen.dimitrov.ext/repos/clank/CLAUDE.md`

Keep the current authoring philosophy. Add sections:

1. **Structure** — point at `docs/` for how-tos, `manifest.toml` as source of truth
2. **Clank's own `.claude/`** — note it's empty; template content lives in `base/` + `addons/`
3. **Hard rules** —
   - Artifacts must not hardcode absolute paths
   - Hooks must bail gracefully if their required tool isn't installed
   - Agents declared read-only must not do write ops via Bash
   - Every new artifact goes in `manifest.toml` or it doesn't ship
   - Every `settings_fragment` must be valid JSON
4. **Source attribution** — ice-scraper + affaan-m
5. **Running tests** — `python -m unittest tests.test_install -v`

- [ ] **Step 1: Edit `CLAUDE.md`**

Append the new sections to the existing authoring philosophy.

- [ ] **Step 2: Commit**

---

## Task 4.9: Final full-stack smoke test

The implementation plan is complete. Run one final end-to-end install against a fresh target using `fullstack-python` (the richest preset) and verify everything works.

- [ ] **Step 1: Install fullstack-python**

```bash
TARGET=$(mktemp -d)
cd /Users/yasen.dimitrov.ext/repos/clank
python install.py --target "$TARGET" --preset fullstack-python --force
```

- [ ] **Step 2: Verify structure**

```bash
find "$TARGET/.claude" -type f | sort
```

Expected: all base + python + typescript + sql artifacts.

- [ ] **Step 3: Validate settings.json**

```bash
cat "$TARGET/.claude/settings.json" | python -m json.tool
```

Expected: PreToolUse has bash-safety, file-safety, mcp-postgres-safety. PostToolUse has ruff, biome, svelte-check.

- [ ] **Step 4: Validate receipt**

```bash
cat "$TARGET/.claude/.clank-installed.json" | python -m json.tool
```

Expected: lists every fullstack-python artifact ID.

- [ ] **Step 5: Round-trip uninstall**

```bash
python install.py --target "$TARGET" --uninstall python-reviewer,ruff,typescript-reviewer,biome
find "$TARGET/.claude" -name "python-reviewer.md" && echo "STILL THERE - FAIL"
find "$TARGET/.claude" -name "ruff-check.sh" && echo "STILL THERE - FAIL"
cat "$TARGET/.claude/settings.json" | python -c "
import json, sys
s = json.load(sys.stdin)
post = s.get('hooks', {}).get('PostToolUse', [])
cmds = []
for e in post:
    cmds.extend(h['command'] for h in e.get('hooks', []))
assert 'ruff-check.sh' not in str(cmds), 'ruff still in settings'
assert 'biome-check.sh' not in str(cmds), 'biome still in settings'
print('settings.json clean')
"
```

- [ ] **Step 6: Run the full installer test suite one more time**

```bash
cd /Users/yasen.dimitrov.ext/repos/clank
python -m unittest tests.test_install -v
```

Expected: all tests pass.

- [ ] **Step 7: Clean up and commit (nothing to commit unless issues were found)**

```bash
rm -rf "$TARGET"
git status
```

Expected: clean working tree.

- [ ] **Step 8: Final summary commit (only if fixes were needed)**

If any fixes were needed during the final smoke test, commit them with:
```bash
git commit -m "fix: address issues found during final fullstack-python smoke test"
```

---

## Plan complete

At this point the clank repo has:
- A working `install.py` with full test coverage
- A complete `manifest.toml` with 5 base agents, 3 base hooks, 9 base rules, 3 base skills, 1 plugin doc, plus python/typescript/go/rust/sql addons
- Every preset installs cleanly against a fresh target
- CI wired via GitHub Actions
- Docs in `docs/` covering install + authoring
- README + CLAUDE.md updated

The repo is ready for use: `git clone git@github.com:blancpain/clank.git && ./install.py --target ~/repos/my-new-project --preset python-sql`.
