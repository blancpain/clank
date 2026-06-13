# Changelog

Dated log of what shipped. Newest first. Append an entry when a feature
lands; keep entries short — the diff is the detail.

## 2026-06-13

- **Installer: per-artifact `gitignore` field + pycache exclusion**: artifacts
  can now declare a `gitignore = [...]` list in `manifest.toml`; the installer
  appends those patterns to the target's `.gitignore` (create-if-missing,
  idempotent — patterns already present by exact line are skipped, never
  duplicated, never removed on uninstall, like scaffolds). `appstore-connect`
  uses it for `__pycache__/` + `*.pyc`. Separately, `_copy_directory` now drops
  `__pycache__/` and `*.pyc` so a skill bundling a `.py` helper never ships
  bytecode cache into a target. Lint validates the field is a list of strings.
  +7 tests (115 total).
- **`appstore-connect` skill (swift addon)**: App Store Connect API + TestFlight
  from the CLI. Step 0 preflight verifies a per-machine API key
  (`~/.appstoreconnect/`) and walks the user through creating one if absent (never
  assumes access). Bundles a no-dependency `asc.py` (ES256 JWT signed via
  `openssl`, stdlib otherwise) for build/validation status, Xcode Cloud build
  logs, and TestFlight group/tester management — writes gated on user
  confirmation — plus an ITMS rejection→fix table (the 90713 icon/`Info.plist`
  trap). Complements `ios-run` (local build/run). Registered in `manifest.toml`
  + the `swift` preset; prompt-only artifact (hard-rule-9 test-exempt), manifest
  lints clean (108 tests pass).

## 2026-06-12

- **Project-docs convention + scaffold artifact type** (`a39c852`): every
  project gets the same three living documents — `docs/plan.md`,
  `CHANGELOG.md`, a `CLAUDE.md` `## Status` pointer — so `/pickup` and
  `/handoff` are project-agnostic. New `scaffold` manifest type seeds the
  files at the target project root (create-if-missing, never overwrite,
  never uninstall; symlink-escape guarded), `base/rules/project-docs.md`
  defines the contract, pickup/handoff read canonical paths first,
  doc-updater audits the plan's "Now" against diffs. CLAUDE.md hard rule 9:
  installer behavior changes ship with deterministic tests (108 passing).
