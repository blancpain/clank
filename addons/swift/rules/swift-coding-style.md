# Swift Coding Style

Follow these Swift-specific conventions in addition to the general coding style guidelines. Lean on the Swift API Design Guidelines — they are the community standard.

## Standards

- Target **Swift 5.9+** language features (macros, Observation, structured concurrency). Prefer Swift 6 strict-concurrency mode for new modules; if staying in Swift 5 mode, say why in the package manifest.
- If the project uses **SwiftFormat** or **SwiftLint**, run it before committing; match the existing config rather than fighting it.
- Prefer **Swift Package Manager** local packages for shared code; keep app targets thin.

## Naming

- **Types/protocols**: PascalCase — `WorkoutSession`, `Syncable`. Protocols describing capability end in `-able`/`-ing` (`Codable`, `Equatable`); protocols describing a role are nouns (`Collection`, `Repository`).
- **Functions/variables**: camelCase. Methods read as grammatical phrases at the call site: `exercises.insert(bench, at: 0)`, not `exercises.insertExercise(bench, index: 0)`.
- **Argument labels** carry the grammar: `func move(from start: Int, to end: Int)`. Omit labels only when the first argument is the obvious direct object (`append(element)`).
- **Booleans** read as assertions: `isCompleted`, `hasChanges`, `canUndo`.
- **Acronyms**: uniform case — `userID`, `urlString`, `HTTPClient`.
- No Hungarian prefixes, no `k` constants, no `_member` underscores (except the synthesized-wrapper underscore).

## Structure

- **Value types first**: model data as `struct` + `enum`; reach for `class` only for identity, shared mutable state, or framework requirements. Mark classes `final` unless designed for inheritance.
- **One concern per extension**: group protocol conformances into dedicated `extension Type: Protocol` blocks rather than one giant type body. `// MARK: -` between sections.
- **Access control is API design**: default to the lowest level that works. In packages, `public` is a promise — add explicit public initializers for public structs (the memberwise init is internal-only).
- **Early exit**: prefer `guard` for preconditions; keep the happy path at the lowest indentation.

## Idioms

- `if let x` shadowing (`if let session`) over `if let session = session`.
- Prefer `map`/`compactMap`/`filter` chains for transformation, but switch to a `for` loop when the chain needs comments to be understood.
- Use trailing-closure syntax for the last closure argument; named arguments when there are two or more closures.
- Avoid `Any`/`AnyObject` and stringly-typed APIs; use enums with associated values for closed sets of states.
- Errors: define domain error enums conforming to `Error` (+ `LocalizedError` if user-facing); throw early, catch where you can act.
