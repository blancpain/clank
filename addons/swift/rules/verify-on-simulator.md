# Verify on the Simulator Before a Release Build

A UI-affecting change must be verified by **running the app on a simulator and
looking at the result** — not by compile-success alone — before you cut a
release/distribution build (a `v*` tag, an Xcode Cloud / TestFlight / App Store
build). A build that compiles green can still render a broken, empty, or ugly
screen.

## Why

A cloud build + TestFlight round-trip is ~20 minutes and burns build quota — far
too slow to use as a UI feedback loop. A local simulator build is ~1–2 minutes.
Catching layout, legibility, and state bugs in the sim first saves cycles and
keeps released builds clean. (Several real "still ugly" iterations have been
avoided this way.)

## How

1. Build to a simulator and install (`xcodebuild -destination 'id=<UDID>'` +
   `xcrun simctl install`).
2. Launch directly onto the changed screen with a `#if DEBUG` launch argument
   the app checks (seed demo data + deep-link to the screen) — **not** UI
   coordinate scripting, which is fragile.
3. Screenshot (`xcrun simctl io <UDID> screenshot`) and **read the image**. Fix
   anything broken, blank, overflowing, or off, and re-screenshot.
4. **Show the user the screenshot and get their sign-off before cutting the
   release build / pushing the tag.** Both verify, with different jobs: the
   agent confirms it *renders* (objective — not crashed/empty/clipped), but UI
   *quality* ("does this look good?") is the **user's** call. This convention
   exists *because* an agent's solo "looks fine" once shipped a screen the user
   had to send back — surfacing the screenshot closes that loop, doubly so when
   you're iterating on the user's own feedback.

The full recipe and the DEBUG-launch-argument pattern live in the **`ios-run`
skill** (§ "Verify a UI change on the simulator"). The project's specific launch
args, simulator name, and bundle id belong in the project's `CLAUDE.md` (the
skill is generic and gets overwritten on reinstall).

## Scope

- Applies to **UI-affecting** changes. Pure logic covered by `swift test` does
  not need a sim run.
- **Watch UI cannot be trusted on the simulator** (WatchConnectivity is flaky
  there) — verify watch-facing changes on a real-device / TestFlight build.
- This complements, not replaces, the test suite and any code review.
