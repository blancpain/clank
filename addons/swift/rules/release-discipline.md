# Release Discipline: Verify on the Simulator, Then Build Incrementally

After each meaningful change — a feature, a big refactor, a bugfix — two habits keep releases
healthy: **verify UI changes on the simulator before any build**, and **don't let changes pile up
unreleased — cut TestFlight builds incrementally**. The first catches broken UI before it costs a
cloud round-trip; the second gets each change onto a real device while it's small and bisectable —
and is the *only* way to test what the simulator can't.

## 1. Verify UI changes on the simulator before a release build

A UI-affecting change must be verified by **running the app on a simulator and looking at the
result** — not by compile-success alone — before you cut a release/distribution build (a `v*` tag,
an Xcode Cloud / TestFlight / App Store build). A build that compiles green can still render a
broken, empty, or ugly screen.

**Why:** a cloud build + TestFlight round-trip is ~20 minutes and burns build quota — far too slow
to use as a UI feedback loop. A local simulator build is ~1–2 minutes. Catching layout, legibility,
and state bugs in the sim first saves cycles and keeps released builds clean. (Several real "still
ugly" iterations have been avoided this way.)

**How:**

1. Build to a simulator and install (`xcodebuild -destination 'id=<UDID>'` + `xcrun simctl install`).
2. Launch directly onto the changed screen with a `#if DEBUG` launch argument the app checks (seed
   demo data + deep-link to the screen) — **not** UI coordinate scripting, which is fragile.
3. Screenshot (`xcrun simctl io <UDID> screenshot`) and **read the image**. Fix anything broken,
   blank, overflowing, or off, and re-screenshot.
4. **Show the user the screenshot and get their sign-off before cutting the release build / pushing
   the tag.** Both verify, with different jobs: the agent confirms it *renders* (objective — not
   crashed/empty/clipped), but UI *quality* ("does this look good?") is the **user's** call. This
   convention exists *because* an agent's solo "looks fine" once shipped a screen the user had to
   send back — surfacing the screenshot closes that loop, doubly so when you're iterating on the
   user's own feedback.

The full recipe and the DEBUG-launch-argument pattern live in the **`ios-run` skill** (§ "Verify a
UI change on the simulator"). The project's specific launch args, simulator name, and bundle id
belong in the project's `CLAUDE.md` (the skill is generic and gets overwritten on reinstall).

**Scope:**

- Applies to **UI-affecting** changes. Pure logic covered by `swift test` does not need a sim run.
- **Watch UI cannot be trusted on the simulator** (WatchConnectivity is flaky there) — verify
  watch-facing changes on a real-device / TestFlight build.
- Complements, not replaces, the test suite and any code review.

## 2. Cut TestFlight builds incrementally — don't let changes pile up

After each major feature (or milestone slice) merges, **proactively offer to cut a TestFlight
build** — "no build since `v0.X.0`; want me to tag `v0.Y.0`?" — instead of letting changes
accumulate unreleased. Surfacing it is on you; **cutting still needs the user's go-ahead** (a `v*`
tag triggers Xcode Cloud, delivers to testers, and burns build quota).

**Why:** a long backlog of unreleased work is hard to test and harder to bisect — and, crucially,
**the simulator can't verify everything**. Sign in with Apple, push, universal links, and real
backend writes under live auth/RLS only run for real on a device / TestFlight build (the sim runs
stubs). Letting a whole authenticated layer accumulate untested-on-device is how a broken real
flow gets discovered late, in a haystack of commits. (This rule exists because exactly that
happened: an entire accounts + community layer — ~14 PRs — reached `main` with no TestFlight build
for weeks.)

**How:**

1. After a feature merges (or a milestone slice completes), check the last build vs `main`:
   `git tag -l 'v*' --sort=-version:refname | head -1`, then the commits since it.
2. If meaningful unreleased work has accumulated — **especially anything only a device can verify**
   (auth, push, universal links, real backend writes) — surface it and recommend a build.
3. On the user's go-ahead, cut the next `v*` tag (`v0.2.0` → `v0.3.0`; the app's `MARKETING_VERSION`
   typically stays fixed at the App-Store-target version, so the `v*` tag is just the build
   trigger), then **monitor it to `VALID` + delivery via the `appstore-connect` skill** (never raw
   `asc.py`).

**Scope:**

- Don't auto-tag — surface and recommend, then act on the go-ahead (tags are shared state: builds,
  testers, quota — see `executing-actions-with-care`).
- Prioritize a build when the change is device-only-verifiable; pure-logic or sim-verifiable
  changes can batch.
