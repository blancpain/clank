# Changelog

Dated log of what shipped. Newest first. Append an entry when a feature
lands; keep entries short — the diff is the detail.

## 2026-11-25

- **`install.py --update`** (`feat/installer-update`). Brings everything in a project's receipt to
  the current clank: untouched files are replaced, edited files get a three-way merge against the
  version they came from, retired artifacts are removed (kept if edited), and a changed settings
  fragment retracts its old entry. Conflicts are left alone and reported; exit 1. The receipt now
  records each installed file's git blob hash and each merged settings fragment, which is what
  makes this exact; older receipts are adopted on first run. New manifest field `replaces`
  (`agent-review` replaces `review`). 20 new tests.
- **MCP server versions pinned** in both wrappers (`@toolbox-sdk/server@1.18.0`,
  `@supabase/mcp-server-supabase@0.19.0`), so a new release cannot change the tools under every
  project at once. The Supabase wrapper now notes that a writable server's notebook tools run SQL
  the safety hook never sees.
- **Docs caught up:** Swift and Supabase added to the addon and preset lists, the "Stop review
  reminder" (never shipped) and "five hook events" wording removed, `docs/plan.md` cleared of the
  downstream cleanup that is now done.

- **Removed the `requires_mcp` manifest field** (`chore/drop-requires-mcp`). It was documented as
  an install-time warning, but `install.py` never read it, and its one remaining use
  (`database-reviewer` -> `postgres`) would be wrong for Supabase projects anyway.

- **Database agents can now reach the database** (`fix/agent-mcp-tools`). `database-reviewer`
  declared `tools: Read, Grep, Glob, Bash` plus `mcpServers: [postgres]`; with a `tools` list, a
  server named in `mcpServers` grants nothing, so the agent never had a query tool (and fell back
  to `psql` or raw API calls, past the safety hook). Its `tools` now name
  `mcp__postgres__*` and `mcp__supabase__execute_sql`. `pipeline-validator` never queries, so its
  `mcpServers` line and `requires_mcp` hint are gone. `docs/authoring-agents.md` documents the rule.

- **Audit against Claude Code 2.1.332: fix what went stale, drop what the harness now does itself**
  (`fix/claude-code-audit`, PR #7).
  - **Hooks:** `exit 1` was never a "warn" — it is a non-blocking hook error, so the push reminder
    and the ALTER/INSERT "get approval" gate gated nothing. `bash-safety` and both MCP safety hooks
    now return `permissionDecision: "ask"` (a real user prompt) instead. `bash-safety` also runs its
    block rules before the push prompt and skips them only when *every* segment is a plain git
    command, closing `git add . && rm -rf x` and `git push; psql -c "DROP TABLE"`. tmux reminder
    removed (Bash has `run_in_background`).
  - **Rules:** every language rule is path-scoped with `paths:` frontmatter (`fullstack-python`
    always-on rules: ~62KB -> ~23KB). Removed `no-inline-comments`, `executing-actions-with-care`
    (duplicates Claude Code's system prompt), and the generated `agents` rule (Claude Code already
    lists agents and descriptions) along with `--refresh-agents` and its generator.
  - **Skill renamed `review` -> `agent-review`:** `/review` is now an alias of the bundled
    `/code-review`.
  - **Agents:** removed hand-written memory-path instructions (`memory: project` injects them) and
    `Edit`/`Write` from read-only reviewers' `tools`; each now states memory files are the only
    thing it may write, since `memory: project` enables write tools regardless.
  - **pg-mcp now runs Google's MCP Toolbox for Databases** (`@toolbox-sdk/server
    --prebuilt=postgres`) instead of the archived `@modelcontextprotocol/server-postgres`. Same
    `.mcp.json` entry and `DB_URL` in `.env`; the wrapper splits the URL into Toolbox's
    `POSTGRES_*` variables (JSON-encoded, because Toolbox pastes them into YAML) and opens
    sessions with `default_transaction_read_only=on` — Toolbox itself is not read-only. Query tool
    renamed `mcp__postgres__query` -> `mcp__postgres__execute_sql` (hook matcher, `querying-db`,
    `database-reviewer` updated). Verified end to end against a local Postgres 18.
  - **Docs:** `plugins.md` rewritten against the current official marketplace; authoring guides
    and CLAUDE.md brought in line. 107 tests pass.

## 2026-06-25

- **`/merge` skill (base): rebase-merge the current branch's PR via `gh`** — new
  `base/skills/merge/SKILL.md` (`disable-model-invocation: true`, slash-command
  only). Resolves the PR from the current branch (or an explicit number/URL/branch
  arg), reports state via `gh pr view --json` (mergeable / review decision / CI
  checks), confirms before the irreversible step, then runs
  `gh pr merge --rebase --delete-branch`. Supports `--auto` (merge-when-checks-pass)
  and refuses on conflicts/failing checks unless explicitly overridden (`--admin`).
  Registered in `manifest.toml` (id `merge`, tags `base`/`git`); 118 tests pass.

## 2026-06-19

- **Swift rule renamed + expanded: `verify-on-simulator` -> `release-discipline`** — folded the
  sim-verify gate and a new "cut TestFlight builds incrementally" section into one
  `addons/swift/rules/release-discipline.md` (manifest id/path + swift preset + `ios-run` SKILL
  cross-refs updated). The cadence half: after each major feature merges, proactively offer a `v*`
  build (confirm before tagging), prioritizing device-only-verifiable work (auth/push/links/real
  backend writes) the simulator can't test. Prompted by a real miss — a whole accounts+community
  layer (~14 PRs) reached `main` untested-on-device.

## 2026-06-16

- **Installer guard: no orphan rule/agent/hook files** — `test_install.py` gained
  `test_every_rule_agent_hook_file_on_disk_is_registered`, the file-based
  analogue of the existing skill-dir orphan check. It fails CI if a rule/agent/
  hook file under `base/`/`addons/` isn't in `manifest.toml` — closing the gap
  that let `verify-on-simulator.md` ship unregistered (the installer reads the
  manifest, not the filesystem). 118 tests pass. CLAUDE.md rule #9 updated.

- **Swift addon: sim-verify-before-release convention** — distilled from a Sisu
  UI-polish session where a cloud build was nearly spent on an unverified
  redesign. New `addons/swift/rules/verify-on-simulator.md` (always-loaded in
  Swift projects): a UI-affecting change must be verified by *running the app on
  a simulator and reading a screenshot* — not compile-success — before cutting a
  release/distribution build (the ~20-min cloud round-trip is too slow to use as
  a UI feedback loop). The **`ios-run` skill** gained the matching recipe (§2a):
  build to the sim, land on the changed screen via a `#if DEBUG` launch arg
  (seed demo data + deep-link, not UI scripting), screenshot, iterate. Rule =
  the *when/why* (enforced, scoped to Swift projects so non-iOS repos get no
  noise); skill = the *how*; project-specific args/sim/bundle id stay in the
  project's CLAUDE.md (the skill is overwritten on reinstall). Installer
  auto-discovers the new rule via `rglob` — no install.py change.

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
