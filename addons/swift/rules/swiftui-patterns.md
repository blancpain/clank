# SwiftUI Patterns

Hard-won SwiftUI conventions. These prevent the bug classes that cost the most debugging time: state loss, render loops, and stale UI.

## State ownership

- **Decide who owns each piece of state, once.** View-owned ephemera (`@State`), app-level models (`@Observable` class injected via `.environment(...)`), parent-owned values handed down (`let` or `@Binding`).
- With the **Observation framework** (`@Observable`, iOS 17+): inject with `.environment(model)`, read with `@Environment(Model.self)`, use `@Bindable` when you need bindings. Do not mix in `ObservableObject`/`@Published` in new code.
- **Never initialize `@State` from a parameter** expecting it to track later changes — it captures only the first value. Derive in `body`, or sync via `.onChange`.
- Keep `body` pure: no mutations, I/O, or logging during render. Side effects go in `.task`, `.onAppear`, `.onChange`.

## Data flow

- Views are cheap, disposable value types — push logic into the model layer; views render state and forward intent.
- `ForEach` needs **stable identity**: `Identifiable` ids that survive reorder/edit. Array indices are only acceptable for static content.
- Lists that edit their elements should pass **bindings into rows** (`ForEach($items) { $item in ... }`) rather than mutating by index lookup.
- For cross-device or cross-screen consistency, a single source of truth (one observable session/controller) beats duplicated `@State` synchronized by hand.

## Navigation & lifecycle

- `NavigationStack` + value-based `navigationDestination` over deprecated `NavigationView`/`NavigationLink(isActive:)`.
- `.task {}` over `.onAppear { Task { ... } }` — it ties the task lifetime to the view and auto-cancels.
- Sheets/covers driven by `Optional` item state (`.sheet(item:)`) beat boolean flags plus a stashed selection — no nil-while-presented races.

## Performance

- Extract subviews when a `body` exceeds ~50 lines — smaller view structs also narrow re-render scope.
- Expensive derived values: compute in the model when state changes, not in `body` on every render.
- `LazyVStack`/`List` for unbounded content; plain `VStack` only for bounded content.

## Multiplatform (iOS + watchOS)

- Shared logic lives in a platform-neutral package; views stay per-platform. Resist the urge to `#if os()` a single view into serving both — watch UI is a different design, not a smaller phone.
- Guard platform-only APIs (`keyboardType`, haptics, digital crown) at the view layer, never in the shared package.
