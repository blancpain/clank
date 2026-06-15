---
name: ios-app-store-setup
description: First-time setup to ship a brand-new iOS app to the App Store / TestFlight via Xcode Cloud — register the App ID + capabilities, create the app record, cloud-managed signing, the Xcode Cloud workflow + TestFlight post-action, the Internal tester group, and the first-build ITMS gotchas. Invoke via /ios-app-store-setup, or when bootstrapping a new iOS app for distribution, wiring Xcode Cloud → TestFlight for the first time, registering a bundle ID / App ID / capabilities, deciding on signing, or hitting first-submission ITMS rejections on a new app.
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

- **Start Condition:** Branch Changes on your release branch (e.g. `main`).
- **Archive** action (iOS), **Deployment Preparation = TestFlight and App Store**.
- **Post-Actions → ＋ → TestFlight Internal Testing → the Internal group**
  (step 5). **Add this on day one** — without it, a `VALID` build sits at
  `READY_FOR_BETA_TESTING` and never reaches testers until manually assigned
  (`appstore-connect` §3).

Cloud-managed signing is automatic once the workflow archives — no certs to
upload.

## 5. Internal tester group

TestFlight → **Internal Testing** → create a group (e.g. "Internal") → add
testers. **Internal testers must already be users on the App Store Connect
team** (Users and Access). Internal testing needs **no Beta App Review**.

## 6. First build → triage

Push to the workflow's branch (or run the workflow). Then with `appstore-connect`:
- build/processing status reaching `VALID` (§1), Xcode Cloud build logs (§2);
- if rejected at delivery, the **ITMS fix table** (§4);
- confirm the build reaches the group (`internalBuildState: IN_BETA_TESTING`, §3).

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
