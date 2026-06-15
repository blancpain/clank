#!/usr/bin/env python3
"""clank — Claude Code template installer.

Copies base + addon artifacts into a target project's .claude/ directory,
merges settings.json fragments, and manages install receipts for uninstall.

See docs/install.md for full reference.
"""

from __future__ import annotations

import argparse
import copy
import json
import shutil
import stat
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

__version__ = "0.1.0"

VALID_TYPES = {
    "agent",
    "hook",
    "rule",
    "skill",
    "external-skill",
    "plugin-doc",
    "mcp",
    "scaffold",
}


class Manifest:
    """Parsed representation of a clank manifest.toml."""

    def __init__(
        self, artifacts: list[dict], presets: dict[str, list[str]], version: int
    ):
        duplicate_ids = sorted(
            {
                a["id"]
                for a in artifacts
                if [x["id"] for x in artifacts].count(a["id"]) > 1
            }
        )
        self._duplicate_ids = duplicate_ids
        self.artifacts = {a["id"]: a for a in artifacts}
        self.presets = presets
        self.version = version

    @classmethod
    def load(cls, path: Path) -> "Manifest":
        """Load and parse a manifest TOML file."""
        with open(path, "rb") as f:
            data = tomllib.load(f)
        return cls(
            artifacts=data.get("artifacts", []),
            presets=data.get("presets", {}),
            version=data.get("version", 0),
        )


def lint_manifest(manifest: Manifest, clank_root: Path) -> list[str]:
    """Validate a manifest and return a list of error strings (empty = clean)."""
    errors: list[str] = []

    if manifest.version != 1:
        errors.append(f"manifest version must be 1, got {manifest.version}")

    if manifest._duplicate_ids:
        errors.append(f"duplicate artifact IDs: {manifest._duplicate_ids}")

    for aid, artifact in manifest.artifacts.items():
        if artifact.get("type") not in VALID_TYPES:
            errors.append(f"{aid}: invalid type {artifact.get('type')!r}")

        gi = artifact.get("gitignore")
        if gi is not None and (
            not isinstance(gi, list) or not all(isinstance(x, str) for x in gi)
        ):
            errors.append(f"{aid}: gitignore must be a list of strings")

        if artifact.get("type") == "external-skill":
            # External skills are fetched at install time via `npx skills add`
            # and live at target/.claude/skills/<skill_name>/ afterwards. They
            # have no source path inside clank.
            if not artifact.get("source"):
                errors.append(f"{aid}: external-skill requires 'source' field")
            if not artifact.get("skill_name"):
                errors.append(f"{aid}: external-skill requires 'skill_name' field")
            if artifact.get("path"):
                errors.append(
                    f"{aid}: external-skill must not define 'path' (fetched via npx)"
                )
            continue

        src = clank_root / artifact["path"]
        if not src.exists():
            errors.append(f"{aid}: path does not exist: {artifact['path']}")

        if artifact.get("type") == "skill" and src.exists() and not src.is_dir():
            errors.append(
                f"{aid}: skill path must be a directory, got file: {artifact['path']}"
            )

        if artifact.get("type") == "scaffold":
            dest = artifact.get("dest")
            if not dest:
                errors.append(f"{aid}: scaffold requires 'dest' field")
            else:
                dest_path = Path(dest)
                if dest_path.is_absolute() or ".." in dest_path.parts:
                    errors.append(
                        f"{aid}: scaffold dest must be relative and stay "
                        f"inside the target: {dest}"
                    )

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

        mcp_frag = artifact.get("mcp_fragment")
        if mcp_frag:
            mcp_frag_path = clank_root / mcp_frag
            if not mcp_frag_path.exists():
                errors.append(f"{aid}: mcp_fragment does not exist: {mcp_frag}")
            else:
                try:
                    json.loads(mcp_frag_path.read_text())
                except json.JSONDecodeError as e:
                    errors.append(f"{aid}: mcp_fragment invalid JSON: {e}")

    known_ids = set(manifest.artifacts.keys())
    preset_names = set(manifest.presets.keys())
    for preset_name, members in manifest.presets.items():
        for member in members:
            if member.startswith("@preset:"):
                ref = member[len("@preset:") :]
                if ref not in preset_names:
                    errors.append(
                        f"preset {preset_name!r}: references unknown preset {ref!r}"
                    )
            elif member.startswith("@tag:"):
                pass  # any tag is allowed; @tag:* is the catch-all
            elif member not in known_ids:
                errors.append(
                    f"preset {preset_name!r}: references unknown artifact {member!r}"
                )

    return errors


class InstallError(Exception):
    """Raised when the installer cannot proceed safely."""


def check_target(target: Path, dry_run: bool = False) -> None:
    """Validate the target directory and create .claude/ if missing.

    If the target itself doesn't exist but its parent is a directory, the
    target is created — this keeps first-time `curl | sh` installs working
    without requiring a prior `mkdir`. If neither the target nor its parent
    exists, the call raises so typo'd paths fail fast. In dry-run mode no
    filesystem writes happen; a notice is printed to stderr instead.
    """
    if not target.exists():
        if not target.parent.is_dir():
            raise InstallError(
                f"target does not exist and its parent is not a directory: {target}"
            )
        if dry_run:
            print(
                f"[dry-run] would create target directory: {target}",
                file=sys.stderr,
            )
        else:
            target.mkdir()
    elif not target.is_dir():
        raise InstallError(f"target is not a directory: {target}")
    if (target / "manifest.toml").exists() and (target / "base").is_dir():
        raise InstallError(f"refusing to install into clank itself: {target}")
    if not dry_run:
        (target / ".claude").mkdir(exist_ok=True)


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

    if artifact.get("type") == "scaffold":
        # Scaffolds seed project content (plan docs, changelogs) at the
        # project root. They are created once and then owned by the project:
        # never overwritten on reinstall, regardless of conflict policy.
        # The manifest lint rejects ".." and absolute dests, but only the
        # filesystem knows about symlinks: an intermediate directory linked
        # outside the target would silently redirect the write.
        try:
            dst.resolve().relative_to(target.resolve())
        except ValueError:
            raise InstallError(
                f"scaffold dest {artifact['dest']!r} resolves outside the "
                f"target (symlink escape?): {dst.resolve()}"
            )
        if dst.exists():
            return False
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        return True

    if artifact.get("type") == "skill":
        return _copy_directory(src, dst, on_conflict)
    copied = _copy_file(src, dst, on_conflict)
    if copied and artifact.get("type") in ("hook", "mcp"):
        st = dst.stat()
        dst.chmod(st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return copied


def _artifact_destination(artifact: dict, target: Path) -> Path:
    """Compute where an artifact lands under target/.claude/.

    Scaffolds are the exception: their manifest `dest` is relative to the
    project root, not `.claude/` — they seed project files like
    `docs/plan.md`. Lint guarantees `dest` is relative and `..`-free.
    """
    if artifact.get("type") == "scaffold":
        return target / artifact["dest"]
    src_path = Path(artifact["path"])
    parts = src_path.parts
    if parts[0] == "base":
        rel = Path(*parts[1:])
    elif parts[0] == "addons":
        rel = Path(*parts[2:])
    else:
        raise InstallError(
            f"artifact path must start with base/ or addons/: {src_path}"
        )
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
) -> bool:
    any_copied = False
    for src_file in sorted(src_dir.rglob("*")):
        if not src_file.is_file():
            continue
        rel = src_file.relative_to(src_dir)
        # Never ship Python bytecode cache into a target — a skill that bundles a
        # .py helper accumulates __pycache__/*.pyc that must not be installed.
        if "__pycache__" in rel.parts or rel.suffix == ".pyc":
            continue
        dst_file = dst_dir / rel
        if _copy_file(src_file, dst_file, on_conflict):
            any_copied = True
    return any_copied


def _apply_gitignore(
    target: Path, patterns: list[str], dry_run: bool = False
) -> bool:
    """Append .gitignore patterns an artifact declares, if not already present.

    Idempotent: patterns already present (exact line, whitespace-stripped) are
    skipped. .gitignore is project-owned content — like scaffolds, these entries
    are appended on install but never removed on uninstall. Returns True if
    anything was (or, in dry-run, would be) added.
    """
    gitignore = target / ".gitignore"
    existing_lines = gitignore.read_text().splitlines() if gitignore.exists() else []
    present = {line.strip() for line in existing_lines}
    missing = [p for p in patterns if p not in present]
    if not missing:
        return False
    if dry_run:
        print(f"[dry-run] add to .gitignore: {', '.join(missing)}")
        return True
    out = list(existing_lines)
    if out and out[-1].strip():
        out.append("")
    header = "# clank-managed"
    if header not in present:
        out.append(header)
    out.extend(missing)
    gitignore.write_text("\n".join(out) + "\n")
    return True


def _external_skill_dir(artifact: dict, target: Path) -> Path:
    """Return the directory where `npx skills add` drops this external skill."""
    return target / ".claude" / "skills" / artifact["skill_name"]


def _install_external_skill(artifact: dict, target: Path) -> bool:
    """Fetch an external skill by shelling out to `npx skills add`.

    Returns True on success, False if npx is missing or the command failed.
    Failures are warnings rather than hard errors — external skills are
    opt-in (default=false) and shouldn't block the rest of the install.

    The `--copy` flag is passed deliberately: `npx skills` symlinks into a
    cache by default, which breaks if the cache is cleared or the project is
    copied to another machine.
    """
    import subprocess

    if shutil.which("npx") is None:
        print(
            f"clank: skipping external-skill {artifact['id']} "
            "(npx not found — install Node.js to fetch external skills)",
            file=sys.stderr,
        )
        return False

    cmd = [
        "npx", "-y", "skills", "add", artifact["source"],
        "--skill", artifact["skill_name"],
        "--copy",
        "-a", "claude-code",
        "-y",
    ]
    try:
        result = subprocess.run(
            cmd,
            cwd=target,
            capture_output=True,
            text=True,
            check=False,
            timeout=180,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        print(
            f"clank: failed to fetch external-skill {artifact['id']}: {e}",
            file=sys.stderr,
        )
        return False

    if result.returncode != 0:
        print(
            f"clank: npx skills failed for {artifact['id']} "
            f"(exit {result.returncode}):\n{result.stderr.strip()}",
            file=sys.stderr,
        )
        return False

    return True


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

    filtered = set()
    for aid in selected:
        if (
            manifest.artifacts[aid].get("default") is False
            and aid not in explicit_includes
        ):
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
            result |= _expand_preset(manifest, member[len("@preset:") :], _seen)
        elif member == "@tag:*":
            result |= {aid for aid in manifest.artifacts}
        elif member.startswith("@tag:"):
            tag = member[len("@tag:") :]
            result |= {
                aid for aid, a in manifest.artifacts.items() if tag in a.get("tags", [])
            }
        else:
            if member not in manifest.artifacts:
                raise ValueError(f"preset {name}: unknown artifact {member}")
            result.add(member)
    return result


def merge_settings(target: dict, fragment: dict) -> dict:
    """Merge a settings.json fragment into an existing target settings dict.

    Only two top-level keys from the fragment are merged into the target:

    - ``hooks`` — hook arrays merge by ``matcher``; within a matched group,
      hook entries dedupe by ``command`` string. This is idempotent: running
      the same merge twice produces the same result.
    - ``permissions.allow`` and ``permissions.deny`` — set-union against the
      target's lists.

    Every other top-level key in the fragment (e.g. ``enabledPlugins``,
    ``model``, ``outputStyle``) is ignored. Clank fragments should never set
    those — the target project owns them, and the installer preserves them.

    The target dict is returned as a deep copy with the above merges applied.
    Target values always win on scalar conflicts in the preserved keys.
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


def merge_mcp(target: dict, fragment: dict) -> dict:
    """Merge an MCP fragment into an existing .mcp.json target dict.

    Adds ``mcpServers`` entries from the fragment. Target entries win on
    key conflict — if the user already configured a server with the same
    name, we leave it alone.

    A fragment server is also skipped when the target already has named
    variants of it — e.g. the fragment ships ``postgres`` but the project
    configured ``postgres-dev`` / ``postgres-mini`` for a multi-DB setup.
    Those variants mean the default server was deliberately replaced, so
    re-adding it on every reinstall would only resurrect a dead entry
    (the default reads ``DB_URL``, which such a project usually doesn't
    define). A target server named ``<fragment-name>-<suffix>`` counts as
    such a variant. Idempotent.
    """
    result = copy.deepcopy(target)
    for server_name, server_config in (fragment.get("mcpServers") or {}).items():
        existing = result.get("mcpServers") or {}
        prefix = server_name + "-"
        if any(name == server_name or name.startswith(prefix) for name in existing):
            continue
        result.setdefault("mcpServers", {})[server_name] = copy.deepcopy(server_config)
    return result


def _parse_agent_frontmatter(path: Path) -> dict[str, str]:
    """Extract name and description from an agent .md file's YAML frontmatter.

    Returns {"name": ..., "description": ...} with empty-string defaults.
    Handles the ``---`` delimited frontmatter that Claude Code agent files use.
    """
    result: dict[str, str] = {"name": path.stem, "description": ""}
    try:
        text = path.read_text()
    except OSError:
        return result
    if not text.startswith("---"):
        return result
    end = text.find("---", 3)
    if end == -1:
        return result
    for line in text[3:end].splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key in ("name", "description"):
            result[key] = value
    return result


def _generate_agents_rule(
    manifest: Manifest,
    installed_ids: set[str],
    target: Path | None = None,
) -> str:
    """Build rules/agents.md content from installed + discovered agent artifacts.

    Returns the full markdown string, or "" if no agents are found.
    The generated file replaces the static base/rules/agents.md so the rule
    always reflects reality — no stale rows for agents the user didn't pick,
    no missing rows for addon agents they did, and custom agents the user
    dropped in by hand are picked up too.

    When *target* is provided, ``.claude/agents/*.md`` is scanned for files
    not covered by the manifest. Their frontmatter is parsed for a name and
    description so they appear in the table alongside manifest-installed agents.
    """
    # 1. Manifest-installed agents: (name, description) from manifest metadata
    agents: list[tuple[str, str]] = []
    manifest_agent_files: set[str] = set()
    for aid in sorted(installed_ids):
        artifact = manifest.artifacts.get(aid)
        if not artifact or artifact.get("type") != "agent":
            continue
        agents.append((aid, artifact.get("description", "")))
        # Track the filename so we can skip it when scanning the target dir
        manifest_agent_files.add(Path(artifact["path"]).name)

    # 2. Discover custom agents the user added manually
    if target is not None:
        agents_dir = target / ".claude" / "agents"
        if agents_dir.is_dir():
            for md_file in sorted(agents_dir.glob("*.md")):
                if md_file.name in manifest_agent_files:
                    continue
                fm = _parse_agent_frontmatter(md_file)
                agents.append((fm["name"], fm["description"]))

    if not agents:
        return ""

    lines = [
        "# Agent Orchestration",
        "",
        "**IMPORTANT: You MUST use these agents proactively.** Do not wait for",
        "the user to ask — invoke the matching agent immediately whenever your",
        "work falls within an agent's purpose.",
        "",
        "| Agent | When to invoke |",
        "|-------|----------------|",
    ]
    for name, desc in agents:
        lines.append(f"| **{name}** | {desc} |")

    lines.extend(
        [
            "",
            "## Parallel Task Execution",
            "",
            "Dispatch agents in parallel when their work is independent.",
            "Multiple Agent tool uses in one assistant message:",
            "",
            "```markdown",
            "# GOOD: Parallel execution",
            "Launch 2 agents in parallel:",
            "1. Agent 1: code-reviewer on the diff",
            "2. Agent 2: security-reviewer on the auth changes",
            "",
            "# BAD: Sequential when unnecessary",
            "First code-reviewer, then wait, then security-reviewer",
            "```",
            "",
            "## Multi-Perspective Analysis",
            "",
            "For complex problems, use split-role subagents in parallel:",
            "- Factual reviewer",
            "- Senior engineer",
            "- Security expert",
            "- Consistency reviewer",
            "",
        ]
    )

    return "\n".join(lines)


END_OF_TURN_BEGIN = "<!-- clank:end-of-turn-review:begin -->"
END_OF_TURN_END = "<!-- clank:end-of-turn-review:end -->"
# Heading used by the generator and by earlier (pre-markers) clank installs.
# Kept as a constant so the writer can locate and replace a legacy section
# that was emitted before the marker comments existed.
END_OF_TURN_HEADING = "### Before ending a coding turn"

# Language-specific reviewer mapping for the end-of-turn table. Each row is
# (trigger label, reviewer agent id). The reviewer is paired with code-reviewer
# when both are installed; rows whose reviewer isn't installed are skipped.
_END_OF_TURN_LANG_ROWS: list[tuple[str, str]] = [
    ("Any Python file", "python-reviewer"),
    ("Any TypeScript/JavaScript file", "typescript-reviewer"),
    ("Any Go file", "go-reviewer"),
    ("Any Rust file", "rust-reviewer"),
]


def _generate_end_of_turn_review(installed_ids: set[str]) -> str:
    """Build the 'Before ending a coding turn' CLAUDE.md block.

    Only emits rows whose referenced agents are installed. Returns "" if no
    review agents are installed at all — the caller should then delete any
    existing block rather than leave a stale one in place.
    """
    rows: list[tuple[str, str]] = []
    code_reviewer = "code-reviewer" in installed_ids

    for label, reviewer in _END_OF_TURN_LANG_ROWS:
        if reviewer not in installed_ids:
            continue
        launch = (
            f"`{reviewer}` + `code-reviewer`" if code_reviewer else f"`{reviewer}`"
        )
        rows.append((label, launch))

    if "sql-reviewer" in installed_ids:
        rows.append(
            ("SQL in any form (raw strings, ORM, migrations)", "`sql-reviewer`")
        )
    if "database-reviewer" in installed_ids and "sql-reviewer" in installed_ids:
        rows.append(
            (
                "SQL migration or schema-changing files",
                "`database-reviewer` + `sql-reviewer`",
            )
        )
    if "pipeline-validator" in installed_ids:
        rows.append(
            (
                "Data-pipeline code (joins, DataFrames, ETL)",
                "`pipeline-validator`",
            )
        )
    if "security-reviewer" in installed_ids:
        rows.append(
            (
                "Security-sensitive changes (auth, crypto, deserialization, input parsing)",
                "`security-reviewer`",
            )
        )
    if code_reviewer:
        rows.append(("Any other code change", "`code-reviewer`"))

    if not rows:
        return ""

    lines = [
        "### Before ending a coding turn",
        "",
        "If the turn modified code, launch the applicable review agents in the",
        "background before concluding your reply. Run in parallel when triggers",
        "overlap.",
        "",
        "| If you touched | Launch |",
        "|---|---|",
    ]
    for label, launch in rows:
        lines.append(f"| {label} | {launch} |")

    lines.extend(
        [
            "",
            "Trivial edits — single-line typo fixes, wording-only doc changes,",
            "constant renames — do not require review.",
        ]
    )

    footer_notes: list[str] = []
    if "docs-researcher" in installed_ids:
        footer_notes.append(
            "`docs-researcher` runs *before* coding when library/API knowledge is "
            "needed (training data may be stale)."
        )
    if "doc-updater" in installed_ids:
        footer_notes.append("`doc-updater` runs once per session, not per turn.")
    if footer_notes:
        lines.append("")
        lines.append(" ".join(footer_notes))

    return "\n".join(lines) + "\n"


def _find_legacy_end_of_turn_span(existing: str) -> tuple[int, int] | None:
    """Locate a pre-markers end-of-turn section by heading.

    Earlier clank versions emitted the section without marker comments, so
    re-running the installer would append a fresh marked copy alongside the
    old one. Detect that case by heading and return the (start, end) slice
    of the legacy section (heading through the line before the next `#`,
    `##`, or `###` heading, or EOF). Returns None if no legacy section is
    present.
    """
    lines = existing.splitlines(keepends=True)
    start_idx: int | None = None
    for i, line in enumerate(lines):
        if line.rstrip("\n") == END_OF_TURN_HEADING:
            start_idx = i
            break
    if start_idx is None:
        return None

    end_idx = len(lines)
    for j in range(start_idx + 1, len(lines)):
        stripped = lines[j].lstrip()
        if stripped.startswith(("# ", "## ", "### ")):
            end_idx = j
            break

    start_offset = sum(len(lines[k]) for k in range(start_idx))
    end_offset = sum(len(lines[k]) for k in range(end_idx))
    return start_offset, end_offset


def _write_end_of_turn_block(target: Path, block: str) -> None:
    """Write (or remove) the end-of-turn block in <target>/CLAUDE.md.

    If *block* is empty, strip any existing block from CLAUDE.md (and delete
    the file if that leaves it empty). Otherwise create CLAUDE.md with the
    block, replace an existing block between the clank markers, replace a
    pre-markers legacy section detected by heading, or append a fresh block
    if neither is present.
    """
    claude_md = target / "CLAUDE.md"
    wrapped = f"{END_OF_TURN_BEGIN}\n{block}{END_OF_TURN_END}\n" if block else ""

    if not claude_md.exists():
        if wrapped:
            claude_md.write_text(wrapped)
        return

    existing = claude_md.read_text()
    begin = existing.find(END_OF_TURN_BEGIN)
    end = existing.find(END_OF_TURN_END)

    if begin != -1 and end != -1 and end > begin:
        end_full = end + len(END_OF_TURN_END)
        # Swallow a single trailing newline so we don't accumulate blank lines
        # across re-installs.
        if end_full < len(existing) and existing[end_full] == "\n":
            end_full += 1
        new = existing[:begin] + wrapped + existing[end_full:]
    else:
        legacy = _find_legacy_end_of_turn_span(existing)
        if legacy is not None:
            start_offset, end_offset = legacy
            # Trim trailing blank lines belonging to the legacy section so the
            # replacement doesn't leave a stack of blank lines behind.
            head = existing[:start_offset].rstrip("\n")
            tail = existing[end_offset:].lstrip("\n")
            if wrapped:
                sep_before = "\n\n" if head else ""
                sep_after = "\n" if tail else ""
                new = head + sep_before + wrapped + sep_after + tail
            else:
                sep = "\n" if head and tail else ""
                new = head + sep + tail
                if new and not new.endswith("\n"):
                    new += "\n"
        elif wrapped:
            sep = "" if existing.endswith("\n") else "\n"
            new = existing + sep + "\n" + wrapped
        else:
            return  # nothing to remove, nothing to add

    if new.strip():
        claude_md.write_text(new)
    else:
        claude_md.unlink()


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
        "installed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "target": str(target.resolve()),
        "artifacts": merged,
    }
    (target / ".claude" / RECEIPT_NAME).write_text(json.dumps(receipt, indent=2) + "\n")


def read_receipt(target: Path) -> dict:
    path = target / ".claude" / RECEIPT_NAME
    if not path.exists():
        return {"artifacts": []}
    return json.loads(path.read_text())


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

        if artifact.get("type") == "external-skill":
            ext_dst = _external_skill_dir(artifact, target)
            if ext_dst.is_dir():
                shutil.rmtree(ext_dst)
            installed.discard(aid)
            continue

        if artifact.get("type") == "scaffold":
            # Scaffolded files become project content the moment they're
            # created (the team's plan, the changelog). Uninstall only
            # forgets the receipt entry — it never deletes the file.
            installed.discard(aid)
            continue

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

        mcp_frag_rel = artifact.get("mcp_fragment")
        if mcp_frag_rel:
            mcp_frag = json.loads((clank_root / mcp_frag_rel).read_text())
            _unmerge_mcp(target, mcp_frag)

        installed.discard(aid)

    if installed:
        write_receipt(
            target,
            sorted(installed),
            receipt.get("clank_version", __version__),
            receipt.get("clank_commit", "unknown"),
        )
        # write_receipt unions with existing, so overwrite the artifacts field cleanly:
        receipt_path = target / ".claude" / RECEIPT_NAME
        data = json.loads(receipt_path.read_text())
        data["artifacts"] = sorted(installed)
        receipt_path.write_text(json.dumps(data, indent=2) + "\n")
    else:
        receipt_path = target / ".claude" / RECEIPT_NAME
        if receipt_path.exists():
            receipt_path.unlink()

    # Regenerate agents.md if an agent was removed but the rule itself remains.
    agents_rule_dst = target / ".claude" / "rules" / "agents.md"
    removed_agents = any(
        manifest.artifacts[aid].get("type") == "agent" for aid in artifact_ids
    )
    if removed_agents and agents_rule_dst.exists() and "agents" not in artifact_ids:
        remaining = set(read_receipt(target).get("artifacts", []))
        content = _generate_agents_rule(manifest, remaining, target)
        if content:
            agents_rule_dst.write_text(content)
        else:
            # No agents left — remove the now-empty rule
            agents_rule_dst.unlink()

    # Rebuild the CLAUDE.md end-of-turn block so it drops uninstalled reviewers.
    if removed_agents:
        remaining = set(read_receipt(target).get("artifacts", []))
        _write_end_of_turn_block(
            target, _generate_end_of_turn_review(remaining)
        )


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
                h
                for h in target_entry.get("hooks", [])
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


def _unmerge_mcp(target: Path, fragment: dict) -> None:
    """Remove MCP servers defined in *fragment* from target/.mcp.json."""
    mcp_path = target / ".mcp.json"
    if not mcp_path.exists():
        return
    mcp = json.loads(mcp_path.read_text())
    servers = mcp.get("mcpServers", {})
    for server_name in fragment.get("mcpServers") or {}:
        servers.pop(server_name, None)
    if not servers:
        mcp.pop("mcpServers", None)
    if mcp:
        mcp_path.write_text(json.dumps(mcp, indent=2) + "\n")
    else:
        mcp_path.unlink()


def install(
    manifest_path: Path,
    clank_root: Path,
    target: Path,
    preset: str | None,
    include: list[str],
    exclude: list[str],
    conflict_policy: str,
    dry_run: bool,
    review_hook_opt_in: bool,
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

    review_hook_id = "review-before-commit"
    if (
        review_hook_id in manifest.artifacts
        and review_hook_opt_in
        and manifest.artifacts[review_hook_id].get("default") is False
    ):
        selected.add(review_hook_id)

    if not selected:
        print("no artifacts selected", file=sys.stderr)
        return 2

    # Validate the target even in dry-run so the preview is honest. See
    # check_target() for the nonexistent-target / auto-create semantics.
    check_target(target, dry_run=dry_run)

    on_conflict = _conflict_callback(conflict_policy)

    copied_ids: list[str] = []
    for aid in sorted(selected):
        artifact = manifest.artifacts[aid]
        if artifact.get("type") == "external-skill":
            dst = _external_skill_dir(artifact, target)
            if dry_run:
                print(
                    f"[dry-run] npx skills add {artifact['source']} "
                    f"--skill {artifact['skill_name']} -> {dst}"
                )
                copied_ids.append(aid)
                continue
            if _install_external_skill(artifact, target):
                copied_ids.append(aid)
            continue
        src = clank_root / artifact["path"]
        dst = _artifact_destination(artifact, target)
        if dry_run:
            # Scaffolds skip silently when the file exists; the preview must
            # say so rather than promise a copy the real run won't do.
            if artifact.get("type") == "scaffold" and dst.exists():
                print(f"[dry-run] skip {dst} (scaffold already exists)")
            else:
                print(f"[dry-run] copy {src} -> {dst}")
            copied_ids.append(aid)
            continue
        copied = copy_artifact(artifact, clank_root, target, on_conflict)
        if copied:
            copied_ids.append(aid)

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

        # Merge MCP fragments into <target>/.mcp.json
        mcp_frags = [
            manifest.artifacts[aid].get("mcp_fragment")
            for aid in copied_ids
            if manifest.artifacts[aid].get("mcp_fragment")
        ]
        if mcp_frags:
            mcp_path = target / ".mcp.json"
            mcp_current = (
                json.loads(mcp_path.read_text()) if mcp_path.exists() else {}
            )
            for frag_rel in mcp_frags:
                frag = json.loads((clank_root / frag_rel).read_text())
                mcp_current = merge_mcp(mcp_current, frag)
            mcp_path.write_text(json.dumps(mcp_current, indent=2) + "\n")

    # .gitignore patterns declared by installed artifacts (e.g. a skill that
    # bundles a Python helper wants __pycache__/ ignored). Applies in dry-run
    # too, as a preview.
    gi_patterns: list[str] = []
    for aid in copied_ids:
        for pat in manifest.artifacts[aid].get("gitignore", []):
            if pat not in gi_patterns:
                gi_patterns.append(pat)
    if gi_patterns:
        _apply_gitignore(target, gi_patterns, dry_run=dry_run)

    if not dry_run and copied_ids:
        write_receipt(target, copied_ids, clank_version, clank_commit)

    # Regenerate agents.md dynamically based on actually-installed agents.
    # Triggers when the agents rule itself is installed, OR when new agent
    # artifacts are added to an existing install that already has the rule.
    if not dry_run:
        agents_rule_dst = target / ".claude" / "rules" / "agents.md"
        new_agents = any(
            manifest.artifacts[aid].get("type") == "agent" for aid in copied_ids
        )
        if "agents" in copied_ids or (agents_rule_dst.exists() and new_agents):
            all_installed = set(read_receipt(target).get("artifacts", []))
            content = _generate_agents_rule(manifest, all_installed, target)
            if content:
                agents_rule_dst.parent.mkdir(parents=True, exist_ok=True)
                agents_rule_dst.write_text(content)

        if new_agents:
            all_installed = set(read_receipt(target).get("artifacts", []))
            _write_end_of_turn_block(
                target, _generate_end_of_turn_review(all_installed)
            )

    print(f"installed: {', '.join(copied_ids) if copied_ids else '(nothing)'}")
    return 0


def _conflict_callback(policy: str) -> Callable[[Path], str]:
    if policy == "overwrite":
        return lambda _dst: "overwrite"
    if policy == "skip":
        return lambda _dst: "skip"
    if policy == "interactive":
        return _InteractiveConflictPrompt()
    raise InstallError(f"unknown conflict policy: {policy}")


class _InteractiveConflictPrompt:
    """Per-file conflict prompt with "apply to all" memory.

    Callable that behaves like ``Callable[[Path], str]``. Once the user
    picks "Skip all" or "Overwrite all", subsequent calls return that
    choice without prompting again.
    """

    def __init__(self) -> None:
        self._all: str | None = None

    def __call__(self, dst: Path) -> str:
        if self._all is not None:
            return self._all
        while True:
            try:
                answer = (
                    input(
                        f"Conflict: {dst} already exists.\n"
                        "  [s]kip / [o]verwrite / [S]kip all / [O]verwrite all"
                        " / [d]iff / [a]bort > "
                    )
                    .strip()
                )
            except EOFError:
                return "skip"

            lower = answer.lower()
            # "All" variants must be checked before single-item variants
            # because "S".lower() == "s" would match single-skip first.
            if answer == "S" or lower == "skip all":
                self._all = "skip"
                return "skip"
            if answer == "O" or lower == "overwrite all":
                self._all = "overwrite"
                return "overwrite"
            if lower in ("", "s", "skip"):
                return "skip"
            if lower in ("o", "overwrite"):
                return "overwrite"
            if lower in ("a", "abort"):
                return "abort"
            if lower in ("d", "diff"):
                try:
                    import subprocess

                    result = subprocess.run(
                        ["head", "-20", str(dst)],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    print(
                        f"--- existing content of {dst.name} (first 20 lines) ---"
                    )
                    print(result.stdout)
                    print("---")
                except Exception as e:
                    print(f"(diff failed: {e})")
                continue
            print(f"Unknown choice: {answer!r}. Pick s/o/S/O/d/a.")


def _seed_settings(clank_root: Path) -> dict:
    base_settings = clank_root / "base" / "settings.json"
    if base_settings.exists():
        return json.loads(base_settings.read_text())
    return {}


def _git_commit(clank_root: Path) -> str:
    # install.sh drops a sidecar .clank-ref file with the fetched git ref
    # (branch/tag/sha) after extracting the tarball, so tarball installs
    # don't log "unknown" in the receipt. Honor it here without requiring a
    # user-facing CLI flag on install.py.
    sidecar = clank_root / ".clank-ref"
    if sidecar.is_file():
        value = sidecar.read_text().strip()
        if value:
            return value

    import subprocess

    try:
        result = subprocess.run(
            ["git", "-C", str(clank_root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()[:12]
    except (FileNotFoundError, subprocess.CalledProcessError):
        return "unknown"


CATEGORIES = [
    ("agent", "Agents"),
    ("hook", "Hooks"),
    ("rule", "Rules"),
    ("skill", "Skills"),
    ("external-skill", "External skills (npx)"),
    ("mcp", "MCP servers"),
    ("plugin-doc", "Plugin docs"),
    ("scaffold", "Project doc scaffolds"),
]


def curses_pick(
    manifest: Manifest, preselected: set[str] | None = None
) -> set[str] | None:
    """Per-category curses checkbox picker, one page per category.

    Walks the user through each CATEGORY in sequence (Agents → Hooks →
    Rules → Skills → Plugin docs). Every row shows a real `[x]` or `[ ]`
    checkbox. Keybindings:

      ↑/↓ or j/k  navigate
      SPACE       toggle current row and advance
      a / A       toggle all rows in the current category
      ENTER       confirm this page and advance to the next category
      ESC or q    abort the whole install

    Returns the union of selections across categories, or None if curses
    is not importable on this platform (callers should fall back to
    interactive_pick()). Raises InstallError on user abort.

    Implementation notes:

    - curses is in Python's stdlib on macOS/Linux; Windows needs an extra
      `windows-curses` package which clank doesn't support anyway
      (install.sh is POSIX-shell-only), so we return None on ImportError
      and let interactive_pick handle the exotic case.
    - `curses.wrapper` handles terminal setup/teardown and guarantees
      endwin() runs even on exceptions, so InstallError raised from
      inside propagates with the terminal properly restored.
    - `set_escdelay(25)` makes bare ESC react snappily (default is 1000ms)
      without breaking arrow-key escape sequences which arrive faster.
    """
    try:
        import curses
    except ImportError:
        return None

    def _picker(stdscr) -> set[str]:
        curses.curs_set(0)  # hide cursor
        curses.set_escdelay(25)
        stdscr.keypad(True)

        # Skip empty categories up-front so the page counter in the footer
        # reflects actual work, not stubs.
        non_empty_pages = [
            (
                artifact_type,
                heading,
                sorted(
                    aid
                    for aid, a in manifest.artifacts.items()
                    if a.get("type") == artifact_type
                ),
            )
            for artifact_type, heading in CATEGORIES
        ]
        non_empty_pages = [p for p in non_empty_pages if p[2]]
        total_pages = len(non_empty_pages)

        selected: set[str] = set(preselected or ())
        # Per-page cursor state so navigating back to a previously visited
        # page drops you where you left off instead of resetting to row 0.
        page_state: dict[int, tuple[int, int]] = {}

        def render_category_page(idx: int) -> str:
            """Render one category page until a navigation key is pressed.

            Returns one of: 'prev', 'next', 'abort'. Mutates `selected`
            and `page_state` as side effects.
            """
            _artifact_type, heading, artifacts_in_cat = non_empty_pages[idx]
            current, scroll = page_state.get(idx, (0, 0))
            while True:
                h, w = stdscr.getmaxyx()
                list_top = 2
                visible = max(1, h - list_top - 1)

                # Keep current row within the visible window.
                if current < scroll:
                    scroll = current
                elif current >= scroll + visible:
                    scroll = current - visible + 1

                stdscr.erase()
                # Header uses ASCII `<` / `>` for page nav instead of
                # unicode `←` / `→` because several popular monospace
                # fonts render the horizontal arrows at different advance
                # widths, making the left arrow visually smaller.
                header = (
                    f"{heading} — up/down nav · SPACE toggle · a toggle all"
                    " · < > page · ENTER confirm · ESC abort"
                )
                stdscr.addnstr(0, 0, header[: w - 1], w - 1, curses.A_REVERSE)

                end = min(len(artifacts_in_cat), scroll + visible)
                for i in range(scroll, end):
                    aid = artifacts_in_cat[i]
                    mark = "[x]" if aid in selected else "[ ]"
                    desc = manifest.artifacts[aid].get("description", "") or ""
                    line = f" {mark}  {aid:28}  {desc}"
                    y = list_top + (i - scroll)
                    attr = curses.A_REVERSE if i == current else curses.A_NORMAL
                    stdscr.addnstr(y, 0, line[: w - 1], w - 1, attr)

                footer = (
                    f"  page {idx + 1}/{total_pages}  ·  "
                    f"{len(selected)} selected"
                )
                if h > list_top:
                    stdscr.addnstr(h - 1, 0, footer[: w - 1], w - 1, curses.A_DIM)

                stdscr.refresh()
                key = stdscr.getch()

                if key in (curses.KEY_UP, ord("k")) and current > 0:
                    current -= 1
                elif (
                    key in (curses.KEY_DOWN, ord("j"))
                    and current < len(artifacts_in_cat) - 1
                ):
                    current += 1
                elif key == ord(" "):
                    aid = artifacts_in_cat[current]
                    if aid in selected:
                        selected.discard(aid)
                    else:
                        selected.add(aid)
                    # Auto-advance after toggle for rapid-tap selection.
                    if current < len(artifacts_in_cat) - 1:
                        current += 1
                elif key in (ord("a"), ord("A")):
                    all_in_cat = set(artifacts_in_cat)
                    if all_in_cat.issubset(selected):
                        selected.difference_update(all_in_cat)
                    else:
                        selected.update(all_in_cat)
                elif key in (curses.KEY_LEFT, ord("h")):
                    page_state[idx] = (current, scroll)
                    return "prev"
                elif key in (
                    curses.KEY_RIGHT,
                    ord("l"),
                    curses.KEY_ENTER,
                    10,
                    13,
                ):
                    page_state[idx] = (current, scroll)
                    return "next"
                elif key in (27, ord("q"), ord("Q")):
                    return "abort"
                elif key == curses.KEY_RESIZE:
                    pass

        def render_review_page() -> str:
            """Render the final review/confirm page.

            Lists every selection grouped by category so the user can
            double-check before committing. ENTER is the only way to
            finish — < / h / ← go back to the last category, ESC/q
            aborts. Returns one of: 'prev', 'finish', 'abort'.
            """
            while True:
                h, w = stdscr.getmaxyx()
                stdscr.erase()
                header = (
                    "Review — up/down scroll · < back · "
                    "ENTER install · ESC abort"
                )
                stdscr.addnstr(0, 0, header[: w - 1], w - 1, curses.A_REVERSE)

                y = 2
                total_selected = 0
                for _artifact_type, heading, artifacts_in_cat in non_empty_pages:
                    picked_count = sum(
                        1 for a in artifacts_in_cat if a in selected
                    )
                    total_selected += picked_count
                    if y >= h - 1:
                        continue  # truncate silently on tiny terminals
                    summary = (
                        f"{heading} ({picked_count}/{len(artifacts_in_cat)})"
                    )
                    stdscr.addnstr(y, 0, summary[: w - 1], w - 1, curses.A_BOLD)
                    y += 1
                    for aid in artifacts_in_cat:
                        if y >= h - 1:
                            break
                        mark = "[x]" if aid in selected else "[ ]"
                        desc = manifest.artifacts[aid].get("description", "") or ""
                        line = f"  {mark}  {aid:28}  {desc}"
                        attr = (
                            curses.A_NORMAL
                            if aid in selected
                            else curses.A_DIM
                        )
                        stdscr.addnstr(y, 0, line[: w - 1], w - 1, attr)
                        y += 1
                    y += 1  # blank line between categories

                if total_selected == 0:
                    footer = (
                        "  nothing selected — press < to go back and pick, "
                        "or ESC to abort"
                    )
                else:
                    footer = (
                        f"  {total_selected} artifacts selected  ·  "
                        "press ENTER to install"
                    )
                if h > 2:
                    stdscr.addnstr(h - 1, 0, footer[: w - 1], w - 1, curses.A_DIM)

                stdscr.refresh()
                key = stdscr.getch()

                if key in (curses.KEY_LEFT, ord("h")):
                    return "prev"
                elif key in (curses.KEY_ENTER, 10, 13):
                    # Only finish if there's at least one selection.
                    # Empty-selection ENTER is a silent no-op so the user
                    # can't accidentally install nothing.
                    if total_selected > 0:
                        return "finish"
                elif key in (27, ord("q"), ord("Q")):
                    return "abort"
                elif key == curses.KEY_RESIZE:
                    pass

        # Dispatcher: walk category pages then the review page. Actions
        # bubble up from the page renderers and mutate `idx`.
        idx = 0
        while True:
            if idx < total_pages:
                action = render_category_page(idx)
            else:  # idx == total_pages — the review page
                action = render_review_page()

            if action == "next":
                idx += 1  # may move onto the review page
            elif action == "prev":
                if idx > 0:
                    idx -= 1
                # else: already on first page, silent no-op
            elif action == "finish":
                return selected
            elif action == "abort":
                raise InstallError("selection aborted")

    try:
        return curses.wrapper(_picker)
    except curses.error:
        # Terminal doesn't support curses (too small, bad TERM, etc).
        # Return None so the caller falls back to interactive_pick.
        return None


def interactive_pick(
    manifest: Manifest,
    input_fn: Callable[[str], str] = input,
    output=None,
    preselected: set[str] | None = None,
) -> set[str]:
    """Numbered-list picker grouped by artifact category.

    Prints the categories one at a time with toggleable checkboxes.
    Accepts: numbers (space- or comma-separated) to toggle, (a)ll, (n)one,
    (c)ontinue to advance to the next category. Returns the set of
    selected artifact IDs. Pure stdlib — no curses/termios dependency.

    When *preselected* is provided, those IDs start checked — handy for
    re-running the installer on a target that already has artifacts.
    """
    out = output if output is not None else sys.stdout
    selected: set[str] = set(preselected or ())

    for artifact_type, heading in CATEGORIES:
        artifacts = sorted(
            aid
            for aid, a in manifest.artifacts.items()
            if a.get("type") == artifact_type
        )
        if not artifacts:
            continue
        while True:
            print(f"\n== {heading} ==", file=out)
            for i, aid in enumerate(artifacts, 1):
                mark = "x" if aid in selected else " "
                desc = manifest.artifacts[aid].get("description", "")
                print(f"  [{mark}] {i:2}. {aid:30} — {desc}", file=out)
            cmd = (
                input_fn("Toggle (numbers), (a)ll, (n)one, (c)ontinue > ")
                .strip()
                .lower()
            )
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


def _resolve_target(args: argparse.Namespace) -> Path:
    """Return an explicit --target, or default to CWD after a confirm prompt.

    Prompting protects users from accidentally installing into `~` or an
    unrelated directory. `--force` and `--dry-run` skip the prompt — force
    because the user has explicitly opted into non-interactive install, and
    dry-run because nothing is written.
    """
    if args.target is not None:
        return args.target
    cwd = Path.cwd()
    if args.force or args.dry_run:
        return cwd
    try:
        answer = input(f"clank: install into {cwd}? [y/N] ").strip().lower()
    except EOFError:
        answer = ""
    if answer not in ("y", "yes"):
        raise InstallError(
            "aborted — pass --target explicitly, or --force to accept CWD"
        )
    return cwd


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="clank",
        description="Install clank .claude/ artifacts into a project",
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=None,
        help="Target project directory (default: current directory, with confirmation)",
    )
    parser.add_argument("--preset", help="Named bundle from manifest.toml")
    parser.add_argument("--include", help="Comma-separated artifact IDs to add")
    parser.add_argument("--exclude", help="Comma-separated artifact IDs to drop")
    parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Pick artifacts via numbered-list prompt",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be copied, write nothing",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite conflicts without prompting",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Print the manifest and exit",
    )
    parser.add_argument(
        "--uninstall",
        help="Comma-separated artifact IDs to uninstall from --target",
    )
    parser.add_argument(
        "--refresh-agents",
        action="store_true",
        help="Regenerate agents.md from installed + discovered agents, then exit",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"clank {__version__}",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    # Thin wrapper around _main_impl so expected user-facing exits surface
    # as clean `clank: <message>` lines instead of Python tracebacks:
    #   - InstallError: target validation, conflict abort, curses ESC/q,
    #     etc. (things we raise ourselves)
    #   - KeyboardInterrupt: Ctrl-C during curses.getch() or the stdlib
    #     input() prompts. curses.wrapper has already restored the
    #     terminal by the time this bubbles up.
    # Any other exception type is still a bug and keeps its traceback.
    try:
        return _main_impl(argv)
    except InstallError as e:
        print(f"clank: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("clank: aborted", file=sys.stderr)
        return 130  # conventional SIGINT exit code (128 + 2)


def _main_impl(argv: list[str] | None) -> int:
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

    if args.uninstall:
        target = _resolve_target(args)
        manifest = Manifest.load(manifest_path)
        ids = [x.strip() for x in args.uninstall.split(",") if x.strip()]
        uninstall(manifest, clank_root, target, ids)
        print(f"uninstalled: {', '.join(ids)}")
        return 0

    if args.refresh_agents:
        target = _resolve_target(args)
        manifest = Manifest.load(manifest_path)
        agents_dst = target / ".claude" / "rules" / "agents.md"
        all_installed = set(read_receipt(target).get("artifacts", []))
        content = _generate_agents_rule(manifest, all_installed, target)
        if content:
            agents_dst.parent.mkdir(parents=True, exist_ok=True)
            agents_dst.write_text(content)
            # Count agents in the generated output
            agent_count = sum(
                1 for aid in all_installed
                if manifest.artifacts.get(aid, {}).get("type") == "agent"
            )
            # Count custom agents from disk
            agents_dir = target / ".claude" / "agents"
            if agents_dir.is_dir():
                manifest_files = {
                    Path(manifest.artifacts[aid]["path"]).name
                    for aid in all_installed
                    if manifest.artifacts.get(aid, {}).get("type") == "agent"
                }
                agent_count += sum(
                    1
                    for f in agents_dir.glob("*.md")
                    if f.name not in manifest_files
                )
            print(f"agents.md refreshed ({agent_count} agents)")
        else:
            if agents_dst.exists():
                agents_dst.unlink()
            print("agents.md removed (no agents found)")

        _write_end_of_turn_block(
            target, _generate_end_of_turn_review(all_installed)
        )
        return 0

    include = [x.strip() for x in (args.include or "").split(",") if x.strip()]
    exclude = [x.strip() for x in (args.exclude or "").split(",") if x.strip()]

    if not args.preset and not include and not args.interactive:
        parser.error("one of --preset, --include, --interactive is required")

    # Resolve target only after we know a selection is viable — avoids
    # prompting the user to confirm CWD only to fail on missing --preset.
    target = _resolve_target(args)

    if args.interactive:
        manifest_for_picker = Manifest.load(manifest_path)
        # Pre-check artifacts that are already installed in the target so the
        # picker reflects current state instead of starting empty.
        already = set(read_receipt(target).get("artifacts", []))
        preselected = already & set(manifest_for_picker.artifacts)
        picked = curses_pick(manifest_for_picker, preselected)
        if picked is None:
            # curses not available (import failed or terminal too small)
            # — fall back to the stdlib numbered picker.
            picked = interactive_pick(manifest_for_picker, preselected=preselected)
        include = sorted(set(include) | picked)

    review_hook_id = "review-before-commit"
    review_hook_opt_in = False
    manifest_preview = Manifest.load(manifest_path)
    if (
        review_hook_id in manifest_preview.artifacts
        and review_hook_id not in include
        and not args.force
        and not args.dry_run
        and not args.interactive
    ):
        answer = (
            input(
                "Include the PreToolUse hook that blocks `git commit` once to "
                "remind you to run code-reviewer? [y/N] "
            )
            .strip()
            .lower()
        )
        review_hook_opt_in = answer == "y"

    policy = "overwrite" if args.force else "interactive"
    return install(
        manifest_path=manifest_path,
        clank_root=clank_root,
        target=target,
        preset=args.preset,
        include=include,
        exclude=exclude,
        conflict_policy=policy,
        dry_run=args.dry_run,
        review_hook_opt_in=review_hook_opt_in,
        clank_version=__version__,
        clank_commit=_git_commit(clank_root),
    )


if __name__ == "__main__":
    sys.exit(main())
