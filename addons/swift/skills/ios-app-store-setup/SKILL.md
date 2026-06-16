---
name: ios-app-store-setup
description: First-time setup to ship a brand-new iOS app to the App Store / TestFlight via Xcode Cloud — register the App ID + capabilities, create the app record, cloud-managed signing, the Xcode Cloud workflow + TestFlight post-action, the Internal tester group, the account-level gates (agreements / DSA trader status / banking), and the first-build ITMS + export-auth gotchas (incl. the manual-upload escape hatch). Invoke via /ios-app-store-setup, or when bootstrapping a new iOS app for distribution, wiring Xcode Cloud → TestFlight for the first time, registering a bundle ID / App ID / capabilities, deciding on signing, hitting first-submission ITMS rejections, or an Xcode Cloud export failing with "Unable to authenticate with App Store Connect".
---

# ios-app-store-setup — bootstrap a new iOS app to App Store / TestFlight

The **one-time** sequence to take a brand-new app from nothing to a TestFlight
build, in dependency order, with the gotchas that bite on the first ship.
Complements `ios-run` (build/run locally) and `appstore-connect` (operate
App Store Connect from the CLI — build status, logs, TestFlight, re-triggers).

Most steps are **manual portal/Xcode actions** — guide the user click-by-click;
only some can be scripted. Do the steps **in order** — capabilities must exist
on the App ID before the first signed build, or the archive export fails.

## 0. Prereqs

- **Apple Developer Program** membership (paid) and a **Team ID**.
- Decide the **bundle ID** (reverse-DNS, e.g. `com.acme.app`) — it's permanent.
- Decide signing: **Xcode Cloud cloud-managed automatic signing** is simplest
  (no manual certs/profiles); this runbook assumes it.
- **Assess before you create.** This skill may run against a *partly* set-up app,
  so check current state via the API before doing anything in a portal. Run the
  `appstore-connect` skill's **Step 0 preflight** first — the API key lives at
  `~/.appstoreconnect/` (use that exact path, don't guess) and often already
  exists. With it, query what's already there: `/v1/apps?filter[bundleId]=<id>`
  (does the app record exist? note its numeric `adamId`) and
  `/v1/bundleIds?filter[identifier]=<id>&include=bundleIdCapabilities` (which App
  ID capabilities are already enabled — automatic signing for *local device*
  builds may have added them already, so step 1 is often already done). Verify,
  don't duplicate.
- **Clear the account-level gates early** — the *non-obvious* blocker that fails
  the **export**, not the build, and costs hours if missed (see §6). App Store
  Connect → **Business → Agreements, Tax, and Banking**: the **Free Apps
  Agreement** must read **Active**; an **EU-based** account must complete its
  **DSA trader status** (a banner prompts you — submit trader info); add
  **banking + the Paid Apps Agreement** *only* if the app has a paid tier / IAP.
  Xcode Cloud uploads via a *non-interactive* session that hard-fails when any of
  these is pending. Apple processes them on its backend (DSA shows "In Review")
  and propagation can take hours — so do them up front.

## 1. Register the App ID + capabilities  ⚠️ do this FIRST

developer.apple.com → **Certificates, Identifiers & Profiles** → **Identifiers**
→ ＋ → **App IDs** → App → set the bundle ID → **enable every capability the app
will use** (Sign in with Apple, Associated Domains, Push, App Groups, …) → Save.

> **The #1 first-ship gotcha.** Cloud-managed signing **cannot add a capability
> to a registered App ID**. If the app's entitlements request a capability the
> App ID doesn't have, the Xcode Cloud **Archive → export** step fails with
> `"Automatic signing cannot update … to enable <Capability>"` + `"No profiles
> for '<bundle id>' were found"`. Enable capabilities here *before* the first
> signed build. (Diagnose such failures with `appstore-connect` §2.)

## 2. Create the app record

App Store Connect → **Apps** → ＋ → **New App**: platform iOS, name, primary
language, the **bundle ID** from step 1, and an SKU. Note the **app id** (the
numeric `adamId`) the API uses.

## 3. Project config that passes Apple's validation

These prevent the standard first-build rejections (set them before build 1):

- **App icon:** a real **1024×1024 opaque (no alpha)** `AppIcon` — single size,
  Xcode auto-generates the device sizes. Avoids **ITMS-90022 / 90023**.
- **Top-level `CFBundleIconName`:** use an **explicit `Info.plist`** with
  `CFBundleIconName=AppIcon`. `GENERATE_INFOPLIST_FILE=YES` does **not** emit it
  (actool writes only the nested `CFBundleIcons`; `INFOPLIST_KEY_CFBundleIconName`
  is ignored). Avoids **ITMS-90713**.
- **Export compliance:** `ITSAppUsesNonExemptEncryption = NO` in `Info.plist`
  (standard HTTPS/TLS) — skips the per-build compliance prompt.
- **Entitlements file** matching the step-1 capabilities (e.g.
  `com.apple.developer.applesignin`, `com.apple.developer.associated-domains`).
- **Commit a shared scheme** — Xcode Cloud ignores `xcuserdata` schemes and
  needs a shared one to archive. (XcodeGen: define it under `schemes:`.)

## 4. Create the Xcode Cloud workflow

App Store Connect → the app → **Xcode Cloud** → **Manage Workflows** → ＋
(or set up from within Xcode — same workflow, editable from both surfaces):

- **Start Condition:** Branch Changes on your release branch (e.g. `main`). With
  **Auto-cancel** on (default), *every* push to that branch — including docs —
  cancels the in-flight build and starts a new one. Add a **Files and Folders**
  condition, or use a tag/manual trigger, if routine commits shouldn't kick off
  (and cancel) builds.
- **Archive** action (iOS), **Deployment Preparation = TestFlight and App Store**.
- **Post-Actions → ＋ → TestFlight Internal Testing → the Internal group**
  (step 5). **Add this on day one** — without it, a `VALID` build sits at
  `READY_FOR_BETA_TESTING` and never reaches testers until manually assigned
  (`appstore-connect` §3).

Cloud-managed signing is automatic once the workflow archives — no certs to
upload.

> **Generated projects (XcodeGen / Tuist) — strongly prefer committing the
> project.** If the `.xcodeproj`/`.xcworkspace` is generated, the **simplest,
> most robust** setup is to **un-gitignore and commit it *and* its
> `Package.resolved`**. That's what most XcodeGen + Xcode Cloud projects do, and
> it sidesteps *both* traps below. (Regen churn in diffs is a small price; one
> well-set-up reference project will spend hours fighting these otherwise.)
>
> If you keep the generated project out of git, you inherit both:
>
> 1. **Onboarding can't find the project.** The web onboarding scans the cloned
>    repo, finds no project/scheme → **set the workflow up from Xcode** (Product →
>    Xcode Cloud → Create Workflow; it reads the open *local* project), not the
>    web UI.
> 2. **SPM resolution is *refused* on the runner.** Xcode Cloud builds with
>    automatic package resolution **disabled** and requires a committed
>    `<proj>.xcodeproj/project.xcworkspace/xcshareddata/swiftpm/Package.resolved`
>    — and `xcodebuild -resolvePackageDependencies` is **refused for the same
>    reason** (it exits non-zero: *"a resolved file is required when automatic
>    dependency resolution is disabled"*). So you must **provide** a resolved
>    file, not resolve one on CI. For an XcodeGen app whose only SPM dependency is
>    a *local* package, the resolved graph lives at `<LocalPackage>/Package.resolved`
>    (e.g. `MyKit/Package.resolved`, *not* in the .xcodeproj) — un-ignore + commit
>    that and `cp` it into the workspace path in `ci_post_clone.sh`.
>
> `ci_scripts/ci_post_clone.sh` runs automatically after clone, before the build:
>
>    ```sh
>    #!/bin/sh
>    set -eu
>    cd "${CI_PRIMARY_REPOSITORY_PATH:-$(dirname "$0")/..}"
>    # 1. recreate gitignored secret config (e.g. an xcconfig from an API URL/key)
>    #    from (secret) workflow ENVIRONMENT VARIABLES — the repo never commits it.
>    # 2. regenerate the project
>    command -v xcodegen >/dev/null 2>&1 || brew install xcodegen
>    xcodegen generate            # Tuist: tuist generate
>    # 3. place the committed Package.resolved where the archive expects it
>    mkdir -p App.xcodeproj/project.xcworkspace/xcshareddata/swiftpm
>    cp MyKit/Package.resolved App.xcodeproj/project.xcworkspace/xcshareddata/swiftpm/Package.resolved
>    ```
>
> The shared scheme (step 3) must be one the regenerated project emits — with
> XcodeGen, declare it under `schemes:` (auto schemes land in gitignored
> `xcuserdata`, invisible to CI).

## 5. Internal tester group

TestFlight → **Internal Testing** → create a group (e.g. "Internal") → add
testers. **Internal testers must already be users on the App Store Connect
team** (Users and Access). Internal testing needs **no Beta App Review**.

> **The tester must ACCEPT the invite — or the app never appears.** Adding a
> tester (UI *or* API) sends a one-time TestFlight invitation and leaves them at
> state `INVITED`; **the app does not show in their TestFlight until they accept
> it** — the "View in TestFlight / Start Testing" link in the email (or the
> push) — which moves them to `INSTALLED`. A tester already `INSTALLED` on
> *another* of your apps still has to accept *this* app's invite. Symptom: your
> other apps show in TestFlight but the new one doesn't. Fix: accept the email;
> if it never arrived or is stuck at `INVITED`, **re-send** it — `appstore-connect`
> → POST `/v1/betaTesterInvitations` (with `app` + `betaTester` relationships).

## 6. First build → triage

Push to the workflow's branch (or run the workflow). Then with `appstore-connect`:
- build/processing status reaching `VALID` (§1), Xcode Cloud build logs (§2);
- if rejected at delivery, the **ITMS fix table** (§4);
- confirm the build reaches the group (`internalBuildState: IN_BETA_TESTING`, §3).

> **Export fails with "Unable to authenticate with App Store Connect" — and the
> escape hatch.** If the build *archives* fine but the **export** fails, pull the
> `LOG_BUNDLE` artifact (`appstore-connect` §2) and read
> `*/app-store-export-archive-logs/*.xcdistributionlogs/IDEDistribution.critical.log`.
> If it says `Account "Session Proxy Provider": Unable to authenticate with App
> Store Connect (… Code=1 "(null)")`, this is **not your config** — it's Xcode
> Cloud's *non-interactive* session blocked by an unresolved **account-level
> gate** (§0: agreements / DSA / banking still pending or propagating) or a known
> Apple-side backend issue. (The `Command line name "app-store" is deprecated`
> line in that log is a **red herring** — Xcode's own export tooling, unrelated
> to the failure.) Complete the §0 gates and give Apple's backend hours to
> propagate.
>
> **Land the first build manually — this is the reliable unblock.** When the
> export auth keeps failing (or you just want the first build *now*), upload
> **interactively from Xcode**: scheme = the app, destination = **Any iOS Device
> (arm64)** → **Product → Archive** → Organizer → **Distribute App → App Store
> Connect → Upload** (keep automatic signing; accept any agreement prompt that
> appears). The interactive path uses your *logged-in* session instead of the
> proxy, so it gets past the wall — **and typically primes the account so
> subsequent Xcode Cloud builds then authenticate too.** A `VALID` build that's
> internal-only still needs to be linked to the Internal group to reach testers
> (`appstore-connect` §3) — and the TestFlight *phone app* can lag 10–15 min
> showing a brand-new app's first build even when `internalBuildState` is already
> `IN_BETA_TESTING`.

## 7. Universal links / Associated Domains (if used)

- Entitlement: `applinks:<host>`, `webcredentials:<host>`.
- Host the AASA at `https://<host>/.well-known/apple-app-site-association` —
  must return **200 + `application/json`**.
- Use **`www`, not the apex**, if the apex redirects: Apple **does not follow
  redirects** when validating AASA, so a `307 apex→www` never validates.

## Hand-off

Once the first build is `VALID` and in TestFlight, ongoing work
(status, logs, re-triggers, tester management, new-build delivery) lives in the
`appstore-connect` skill. This skill is the one-time bootstrap only.
