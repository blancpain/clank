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
    if not args.target and not args.list:
        parser.error("--target is required unless --list is given")
    return 0


if __name__ == "__main__":
    sys.exit(main())
