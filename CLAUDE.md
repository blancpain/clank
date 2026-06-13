# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Status

Current focus: **none in flight** — `appstore-connect` skill (swift addon)
shipped 2026-06-13. Read `docs/plan.md` before starting work; `CHANGELOG.md`
logs what shipped.

## Purpose

`clank` is a template repository for Claude Code customizations — sub-agents, skills, hooks, and rules — that the user copies or references when starting new projects. It is not an application; there is no build, test, or lint pipeline. The "source code" here is configuration and prompts that shape how Claude Code behaves in downstream projects.

When adding something new, the question to ask is not "does this work in clank" but "is this reusable enough to drop into a fresh project." Prefer self-contained artifacts with minimal assumptions about the surrounding repo.

## Layout conventions

Claude Code discovers customizations from well-known paths. When creating new artifacts in this repo, use these locations so they can be copied verbatim into a project's `.claude/` directory (or into `~/.claude/` for user-global versions):

- `.claude/agents/<name>.md` — sub-agent definitions. Frontmatter declares `name`, `description`, `tools`, and optionally `model`; the body is the agent's system prompt. The `description` field is what the main Claude uses to decide when to delegate, so write it for that selection step, not as human documentation.
- `.claude/skills/<name>/SKILL.md` — skills. Frontmatter `name` and `description` govern when the skill activates; supporting files live alongside `SKILL.md` in the same directory and are loaded on demand.
- `.claude/settings.json` — hooks and other harness configuration. Hooks are shell commands the harness runs on events (`PreToolUse`, `PostToolUse`, `UserPromptSubmit`, etc.); Claude does not execute them, so they must be self-contained shell snippets.
- `.claude/rules/<topic>.md` — rule fragments referenced from `CLAUDE.md` or from agent/skill prompts. Keep each rule file scoped to one topic so it can be included selectively.

Sub-agents, skills, and hooks are orthogonal mechanisms — pick deliberately:
- **Sub-agent** when the work needs its own context window or a restricted tool set (research, review, parallelizable investigations).
- **Skill** when the behavior is a reusable procedure Claude should follow in the main conversation (a workflow, a checklist, a domain-specific method).
- **Hook** when the behavior must run deterministically outside the model's control (formatting on save, blocking a command, injecting context on prompt submit).

## Authoring notes

- Frontmatter `description` fields are matched against user intent by the harness. Be concrete about triggers ("use when the user asks to…") rather than describing capabilities abstractly.
- Skills and agents should not hardcode paths from this template repo. Write them so they work after being copied into an arbitrary project root.
- Hooks in `settings.json` should fail safe — a broken hook can block every tool call until it's fixed.

## Repository structure

- `manifest.toml` — the source of truth for every shipped artifact. Every new artifact goes here or it doesn't ship. The installer reads the manifest, not the filesystem.
- `install.py` — the installer. Stdlib Python 3.11+ only (uses `tomllib`, `shutil`, `json`, `argparse`). Tested via `tests/test_install.py`.
- `base/` — language-agnostic artifacts (agents, hooks, rules, skills, plugins, settings.json, settings.fragments/). Copied into `<target>/.claude/` regardless of language preset. The `base/` prefix is stripped at install time.
- `base/templates/` — scaffold sources (manifest type `scaffold`). Unlike every other artifact these land at the **target project root** (manifest `dest`, e.g. `docs/plan.md`, `CHANGELOG.md`), are created only when missing, and are never overwritten or uninstalled — they seed project content the project then owns. The convention they implement lives in `base/rules/project-docs.md`.
- `addons/<lang>/` — per-language specializations (python, typescript, go, rust, sql). Only copied if the selected preset includes that language. The `addons/<lang>/` prefix is stripped; everything lands under `<target>/.claude/` with the same structure as `base/`.
- `docs/` — authoring guides (`authoring-agents.md`, `authoring-hooks.md`, `authoring-skills.md`, `authoring-rules.md`, `adding-an-addon.md`) and the install reference (`install.md`). These are clank's own documentation and are NOT copied into target projects.
- `tests/` — stdlib unittest tests for the installer. Run via `python3 -m unittest tests.test_install -v`.
- `.github/workflows/test.yml` — CI that runs the test suite on push and PR.

## Clank's own `.claude/`

clank itself does not have an active `.claude/` directory. The template content lives in `base/` and `addons/`, which are NOT picked up by Claude Code when you're editing clank itself. This is intentional — it prevents clank's template artifacts from self-activating. When working on clank, Claude Code operates without the agents, hooks, and rules that the template installs into other projects.

## Hard rules

Non-negotiable when adding or editing artifacts:

1. **Artifacts must not hardcode absolute paths** — use relative paths from the project root, or `$CLAUDE_PROJECT_DIR` in hooks/settings. Downstream projects live at arbitrary paths.
2. **Hooks must bail gracefully** — exit 0 if the required tool (ruff, biome, golangci-lint, etc.) isn't installed. Never let an addon break installs on projects that don't have the tool.
3. **Agents declared read-only must never write** — no `Edit`, no `Write`, no `chmod`/`mkdir`/`touch`/`tee` via Bash. If the agent definition says read-only, enforce it through the `tools` list.
4. **Every new artifact goes in `manifest.toml`** or it doesn't ship — the installer reads the manifest, not the filesystem. A file placed in `base/` or `addons/` without a manifest entry will never be installed.
5. **Every `settings_fragment` must be valid JSON** — the manifest lint step verifies this at install time. A malformed fragment aborts the install before touching the target.
6. **Skill paths are directories, agent/hook/rule/plugin-doc paths are files.** Don't mix. The installer maps type to destination differently for skills vs. file-based artifacts.
7. **Hooks are executable** — run `chmod +x` after creating a hook script. The installer preserves the executable bit, but the source file in clank must already be executable.
8. **Lift and strip, don't invent** — when adapting content from an upstream source (e.g. affaan-m), keep the proven content and strip the project-specific parts. Don't rewrite from scratch unless there's genuinely no source material to work from.
9. **Every installer behavior change ships with tests** — new artifact types, manifest fields, lint rules, copy/merge/uninstall semantics, CLI flags: each gets deterministic coverage in `tests/test_install.py` before it merges (happy path + the guard rails, e.g. "never overwrites", "lint rejects X"). Prompt-only artifacts (agents/skills/rules content) are exempt, but their *registration* is still covered by the real-manifest lint test — which is also why every new artifact must land in `manifest.toml` in the same change (rule 4): `test_real_manifest_lints_clean` only protects what the manifest declares.

## Running tests

```bash
python3 -m unittest tests.test_install -v
```

Tests cover: manifest loading and lint, selection resolution (preset expansion, @tag:*, @tag:<name>, default=false), copy logic (file vs. directory), settings.json merge (hook arrays, permissions), install receipt writing and updating, uninstall round-trip, scaffold semantics (copy-if-missing, never-overwrite, uninstall keeps the file), full `install()` orchestration, and the interactive picker.

## Source attribution

- **affaan-m/everything-claude-code** — source for the per-language `common-<topic>` rules pattern and for `rules/common/agents.md`, `rules/common/testing.md`, `rules/common/coding-style.md`. The addon taxonomy (coding-style / testing / security / patterns per language) follows the split established there.
