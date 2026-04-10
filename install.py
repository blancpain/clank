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

VALID_TYPES = {"agent", "hook", "rule", "skill", "plugin-doc"}


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

        src = clank_root / artifact["path"]
        if not src.exists():
            errors.append(f"{aid}: path does not exist: {artifact['path']}")

        if artifact.get("type") == "skill" and src.exists() and not src.is_dir():
            errors.append(
                f"{aid}: skill path must be a directory, got file: {artifact['path']}"
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


def check_target(target: Path) -> None:
    """Validate the target directory and create .claude/ if missing."""
    if not target.exists():
        raise InstallError(f"target does not exist: {target}")
    if not target.is_dir():
        raise InstallError(f"target is not a directory: {target}")
    if (target / "manifest.toml").exists() and (target / "base").is_dir():
        raise InstallError(f"refusing to install into clank itself: {target}")
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

    if artifact.get("type") == "skill":
        return _copy_directory(src, dst, on_conflict)
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
        dst_file = dst_dir / rel
        if _copy_file(src_file, dst_file, on_conflict):
            any_copied = True
    return any_copied


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
    return lambda _dst: "overwrite"


def _seed_settings(clank_root: Path) -> dict:
    base_settings = clank_root / "base" / "settings.json"
    if base_settings.exists():
        return json.loads(base_settings.read_text())
    return {}


def _git_commit(clank_root: Path) -> str:
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
    ("plugin-doc", "Plugin docs"),
]


def interactive_pick(
    manifest: Manifest,
    input_fn: Callable[[str], str] = input,
    output=None,
) -> set[str]:
    """Numbered-list picker grouped by artifact category.

    Prints the categories one at a time with toggleable checkboxes.
    Accepts: numbers (space- or comma-separated) to toggle, (a)ll, (n)one,
    (c)ontinue to advance to the next category. Returns the set of
    selected artifact IDs. Pure stdlib — no curses/termios dependency.
    """
    out = output if output is not None else sys.stdout
    selected: set[str] = set()

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
        "--version",
        action="version",
        version=f"clank {__version__}",
    )
    return parser


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

    if args.interactive:
        manifest_for_picker = Manifest.load(manifest_path)
        picked = interactive_pick(manifest_for_picker)
        include = sorted(set(include) | picked)

    stop_id = "stop-review-reminder"
    manifest_preview = Manifest.load(manifest_path)
    stop_hook_opt_in = False
    if (
        stop_id in manifest_preview.artifacts
        and stop_id not in include
        and not args.force
        and not args.dry_run
    ):
        answer = (
            input(
                "Include the stop hook that reminds you to run code-reviewer "
                "on code changes? [y/N] "
            )
            .strip()
            .lower()
        )
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


if __name__ == "__main__":
    sys.exit(main())
