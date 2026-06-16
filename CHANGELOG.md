# Changelog

Dated log of what shipped. Newest first. Append an entry when a feature
lands; keep entries short — the diff is the detail.

## 2026-06-16

- **`ios-app-store-setup` skill: hardened from a real first ship** (hours of
  going in circles bringing a new XcodeGen + Xcode Cloud app to TestFlight,
  distilled): (1) lead with **commit the generated `.xcodeproj` + `Package.resolved`**
  — Xcode Cloud disables on-runner SPM resolution and *refuses*
  `xcodebuild -resolvePackageDependencies`, so a committed resolved file copied
  into the workspace by `ci_post_clone.sh` is the fix, not resolving on CI;
  (2) new §0 **account-level gates** (Free Apps agreement / EU **DSA trader
  status** / banking) that fail the *export*, not the build; (3) §6 **export-auth
  triage** — `"Session Proxy Provider: Unable to authenticate with App Store
  Connect"` is an account/Apple-side gate, not config (and the `"app-store"
  deprecated` log line is a red herring), plus the **manual interactive upload
  from Xcode** escape hatch that lands the first build and primes the account;
  (4) the `Start Condition` **auto-cancel** caveat; (5) internal testers must
  **accept the TestFlight invite** (`INVITED` → `INSTALLED`) or the app never
  appears on their device — re-send via `POST /v1/betaTesterInvitations`.

## 2026-06-15

- **`ios-app-store-setup` skill: assess-first + generated-project guidance**:
  added a Step 0 "assess before you create" pointer (run the `appstore-connect`
  preflight, query the existing app record + App ID capabilities before any
  portal action — verify, don't duplicate) and a Step 4 callout for generated
  projects (XcodeGen/Tuist) with a gitignored `.xcodeproj`: onboard Xcode Cloud
  from Xcode (the web UI can't see the project) plus a `ci_post_clone.sh` that
  regenerates the project and recreates gitignored secret config from workflow
  env vars. Both prompted by gaps hit during a real first-time TestFlight setup.
- **installer: MCP merge skips the default server when named variants exist**:
  `merge_mcp` no longer re-adds a fragment's default server (e.g. `postgres`)
  when the target already configured named variants of it (`postgres-dev`,
  `postgres-mini`). Previously a multi-DB project got the dead default
  `postgres` (reads `DB_URL`, which it doesn't define) re-added on every
  reinstall. A target server named `<fragment-name>-<suffix>` now counts as a
  variant and suppresses the default. Tests added.
- **`ios-app-store-setup` skill (swift addon)**: first-time bootstrap runbook for
  shipping a new iOS app to App Store / TestFlight via Xcode Cloud — App ID +
  capabilities (capabilities-before-signing is the #1 gotcha), app record, cloud
  signing, the workflow + TestFlight Internal post-action from day one, the
  Internal tester group, and the first-build ITMS fixes (90022/90023 icon, 90713
  `CFBundleIconName`, export compliance, www-not-apex AASA). Added to the `swift`
  preset; complements `appstore-connect` (ongoing API ops) and `ios-run` (local).
- **`appstore-connect` skill: build→group assignment + delivery states**: added
  the recipe to assign a `VALID` build to an internal group
  (`POST /v1/betaGroups/{id}/relationships/builds`), the `READY_FOR_BETA_TESTING`
  → `IN_BETA_TESTING` semantics, and the `hasAccessToAllBuilds`-is-misleading
  gotcha (builds stay explicitly linked).

## 2026-06-14

- **`appstore-connect` `asc.py`: preflight on missing credentials**: the helper
  now checks `ASC_ISSUER_ID` / `ASC_KEY_ID` and the `.p8` up front and exits with
  actionable setup guidance instead of a bare `KeyError`/openssl traceback. The
  friendly "create a key" path no longer depends on the agent running the skill's
  Step 0 — the tool self-explains on any machine where access isn't configured.
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
