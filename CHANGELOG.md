# Changelog

Dated log of what shipped. Newest first. Append an entry when a feature
lands; keep entries short — the diff is the detail.

## 2026-06-14

- **`appstore-connect` skill: fire on build-failure investigations + re-trigger recipe**:
  rewrote the skill `description` so it surfaces proactively when an Xcode Cloud
  build *fails* / "investigate why a build failed" / archive/export/signing/
  provisioning errors — previously it only advertised delivery (ITMS) rejections,
  so a "builds N failed, investigate why" prompt didn't match. Added a §2 recipe
  for reading export-failure causes out of the `LOG_BUNDLE` `IDEDistribution*.log`
  (e.g. an entitlement whose capability isn't enabled on the App ID) and for
  triggering/re-running a build via `POST /v1/ciBuildRuns`.
- **`branch-per-feature` rule: standalone prose docs skip the branch + PR**: added
  an exception so doc-only edits (`README`, `CHANGELOG`, `docs/`, `plan.md`,
  `CLAUDE.md`) commit straight to `main` — no branch, no PR. Behavioral config
  (`.claude/rules/*`, skills, hooks, agents) and code, plus docs that accompany a
  code change, keep the branch/PR flow.
- **Project-docs convention: ban time/effort estimates in plans**: added a rule
  to `base/rules/project-docs.md` and a note to `base/templates/plan.md`
  prohibiting duration/effort sizing on plan items (`~2 wks`, story points) —
  meaningless under agent execution and stale on contact; order by priority and
  dependency instead. Real external dates (expiries, ramp/cleanup, deadlines)
  are explicitly kept, since `/pickup` checks them as time bombs.

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
