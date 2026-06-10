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
