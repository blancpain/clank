# Swift Testing

Conventions for testing Swift packages and apps.

## Framework

- **Swift Testing** (`import Testing`, `@Test`, `#expect`, `#require`) for new code — not XCTest. It ships with the Swift 6+ toolchain and runs via `swift test`.
- XCTest remains only for UI tests (`XCUITest`) and performance tests (`measure`), which Swift Testing doesn't cover yet.
- A throwing expression inside `#require(...)` needs its own `try`: `try #require(try repo.load(id))`.

## Structure

- `@Suite` structs group related tests; use the suite's `init()` for per-test setup — each test gets a fresh suite instance.
- Name tests as behavior statements: `routineRoundTripsWithSetsAndSupersets`, not `testSave2`.
- Parameterized tests (`@Test(arguments:)`) over copy-pasted near-identical tests.

## What to test where

- **Shared package (models, persistence, sync logic)**: this is where the real coverage belongs — it's UI-independent and runs on macOS in CI without simulators. Keep app targets thin so this layer covers the logic.
- **Persistence**: test against a real in-memory database (e.g. GRDB `DatabaseQueue()`), not mocks — schema bugs (type affinity, encoding strategies, cascade rules) only surface on a real store. Always test full round-trips (write → read → compare), not just writes.
- **Merge/sync logic**: simulate both sides — construct divergent states, merge, assert both edits survive. Test the conflict cases explicitly, including "same record edited on both devices".
- **UI**: prefer extracting view-model logic into testable functions over slow `XCUITest` coverage; reserve UI tests for the few critical flows.

## Discipline

- Tests must not depend on wall-clock time or ordering: inject dates, use fixed `Date(timeIntervalSince1970:)` values.
- A test that exercises only the mock proves nothing — if everything is stubbed, delete the test or test deeper.
- Run `swift test` (or the project's test script) before claiming a change works; paste failures verbatim rather than summarizing them away.
