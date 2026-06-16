---
name: ios-run
description: "Build, install, and run iOS/watchOS apps on simulators or physical devices from the CLI — xcodebuild, simctl, devicectl, signing, paired watch simulators. Invoke via /ios-run or when asked to run/verify an Apple-platform app."
---

# ios-run — drive Apple-platform apps from the CLI

Procedures for building and running iOS/watchOS apps without opening the Xcode GUI. Work through the relevant section; don't skip the verification steps.

## 0. Preflight (always)

```sh
xcode-select -p                 # must point at /Applications/Xcode.app/..., not CommandLineTools
xcodebuild -version
```

- If it points at CommandLineTools: `sudo xcode-select -s /Applications/Xcode.app` (user must run — suggest `! sudo ...`).
- License errors → user runs `! sudo xcodebuild -license accept`.
- "Platform not installed" errors (Xcode 26+ ships platforms separately): `xcodebuild -downloadPlatform iOS` (and `watchOS` if needed) — multi-GB, run in background.
- If the project uses XcodeGen (`project.yml` present), regenerate before building: `xcodegen generate`.

## 1. Build for simulator (no signing needed)

```sh
xcodebuild -project App.xcodeproj -scheme App \
  -destination 'generic/platform=iOS Simulator' build CODE_SIGNING_ALLOWED=NO \
  2>&1 | grep -E "error|BUILD"
```

Always pipe through a grep for `error|BUILD` — full xcodebuild output drowns the signal.

## 2. Run on a simulator

```sh
xcrun simctl list devices available            # find or create one
xcrun simctl create "Dev iPhone" <devicetype-id> <runtime-id>
xcrun simctl boot <UDID>
xcodebuild ... -destination 'id=<UDID>' -derivedDataPath build build CODE_SIGNING_ALLOWED=NO
xcrun simctl install <UDID> build/Build/Products/Debug-iphonesimulator/App.app
xcrun simctl launch <UDID> <bundle-id> [launch-args]
sleep 3 && xcrun simctl io <UDID> screenshot /tmp/app.png   # verify visually — read the PNG
```

- **Verify by screenshot**, not by exit code: a successful launch can still render a blank/crashed view.
- For automated flows that need app state (e.g. "start a workout"), prefer adding a debug launch argument the app checks (`CommandLine.arguments.contains("--autostart-x")`) over UI scripting.

## 2a. Verify a UI change on the simulator before shipping a release build

A local simulator build is ~1–2 min; a cloud build + TestFlight round-trip is
~20 min — far too slow to use as a UI feedback loop, and it burns build quota.
**Before cutting a release/distribution build (a `v*` tag, Xcode Cloud,
TestFlight, App Store), build to the sim, launch onto the changed screen,
screenshot, read it, and iterate locally — only release once it looks right.**
This is enforced by the `verify-on-simulator` rule; this section is the recipe.

The reliable way to land on a specific screen with the right state is a **DEBUG
launch argument the app checks** — not UI scripting (coordinate taps are
fragile). Define the args under `#if DEBUG` so they never ship: a *seed* hook so
data-driven screens populate, and/or a *deep-link* hook that selects the
tab/route:

```swift
// In the root view's .task (or App init), gated #if DEBUG:
if CommandLine.arguments.contains("--seed-demo-data") { await model.seedDemoDataIfEmpty() }
if CommandLine.arguments.contains("--screen-x") { /* select that tab / route */ }
```

```sh
UDID=$(xcrun simctl list devices | grep "<sim name>" | grep -oE '[0-9A-F-]{36}' | head -1)
xcrun simctl boot "$UDID" 2>/dev/null; open -a Simulator
xcodebuild -scheme <Scheme> -destination "id=$UDID" build 2>&1 | grep -E "error:|BUILD"
APP=$(ls -dt ~/Library/Developer/Xcode/DerivedData/<Scheme>-*/Build/Products/Debug-iphonesimulator/<App>.app | head -1)
xcrun simctl install "$UDID" "$APP"
xcrun simctl terminate "$UDID" <bundle-id> 2>/dev/null
xcrun simctl launch "$UDID" <bundle-id> --seed-demo-data --screen-x
sleep 4 && xcrun simctl io "$UDID" screenshot /tmp/verify.png   # then Read the PNG
```

- **Get the user's sign-off**: reading the PNG yourself catches *broken* (blank,
  crashed, clipped); for *looks good*, surface the screenshot to the user and get
  their OK before cutting the release tag — UI quality is the user's call, not
  the agent's (this is the `verify-on-simulator` rule).
- **Seed-hook safety**: if writes enqueue cloud-sync / pending changes, guard the
  seed to run only when signed out *and* local data is empty, so demo rows never
  upload; run the writes off the main thread.
- `sleep` a few seconds before screenshotting data-dependent screens (async
  loads/recomputes must settle).
- Keep the project's specific args, sim name, and bundle id in the **project's
  CLAUDE.md** — they can't live in this skill, which is installed from clank and
  overwritten on reinstall.
- **Watch UI can't be trusted on the simulator** (WatchConnectivity is flaky
  there) — watch-facing changes still need an on-device build.

## 3. Paired iPhone + Apple Watch simulators

```sh
PHONE=$(xcrun simctl create "Dev iPhone" <iphone-type> <ios-runtime>)
WATCH=$(xcrun simctl create "Dev Watch" <watch-type> <watchos-runtime>)
xcrun simctl pair $WATCH $PHONE
xcrun simctl boot $PHONE && xcrun simctl boot $WATCH
```

- Building the iPhone scheme also builds an embedded watch app; install it on the watch sim directly from `App.app/Watch/WatchApp.app`.
- WatchConnectivity works between paired simulators — good enough for sync verification, but flaky vs real hardware; treat real-device testing as the source of truth.

## 4. Physical device (signing required)

```sh
xcrun devicectl list devices                   # device must be cabled, unlocked, trusted, Developer Mode on
xcodebuild -project App.xcodeproj -scheme App \
  -destination 'id=<DEVICE-UDID>' -derivedDataPath build-device \
  -allowProvisioningUpdates build 2>&1 | grep -E "error|Signing|BUILD"
xcrun devicectl device install app --device <DEVICE-UDID> build-device/Build/Products/Debug-iphoneos/App.app
xcrun devicectl device process launch --device <DEVICE-UDID> <bundle-id>
```

Signing gotchas, in the order you'll hit them:

- **No team set**: a signed-in Xcode account's teams (incl. the free Personal Team) are readable via
  `defaults read com.apple.dt.Xcode IDEProvisioningTeams` — use the `teamID` as `DEVELOPMENT_TEAM`.
- **"Bundle identifier cannot be registered"**: the ID is taken globally — bundle IDs are unique across all Apple developers. Switch to a unique reverse-DNS ID.
- **"Team has no devices"**: build against the *concrete* device destination (`id=<UDID>`), not `generic/platform=iOS` — only then does `-allowProvisioningUpdates` register the device and mint profiles.
- **Launch fails with "not explicitly trusted"**: the user must open the app icon once (gets "Untrusted Developer"), then Settings → General → VPN & Device Management → trust the developer. The menu item only appears *after* the first launch attempt.
- Free Personal Team limits: 7-day app expiry, no TestFlight, restricted capabilities. Paid team ID replaces it in one setting.

## 5. Watch app on a physical watch

The watch installs over the air from the paired iPhone: install the iOS app (with embedded watch app) on the phone, then iPhone Watch app → General → Available Apps → install. Watch must be paired, on-wrist/unlocked, and near the phone.

## 6. Cleanup

Add derived-data paths (`build/`, `build-device/`) to `.gitignore` **before** the first build — they're hundreds of MB and accidentally committing them bloats `.git` permanently (requires history rewrite + gc to undo).
