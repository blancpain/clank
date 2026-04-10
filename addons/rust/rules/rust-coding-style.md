# Rust Coding Style

Follow these Rust-specific conventions in addition to the general coding style guidelines. Rust has strong community conventions — `cargo fmt` and `cargo clippy` enforce most of them automatically.

## Standards

- Run **`cargo fmt`** on every file before committing. Configure your editor to format on save.
- Run **`cargo clippy -- -D warnings`** in CI. Clippy warnings become errors.
- Use **`cargo check`** during development for fast feedback without full compilation.
- Target the Rust edition specified in `Cargo.toml` (`edition = "2021"` for new projects).

## Naming

### Functions and Variables

- `snake_case` for functions, variables, modules, crate names, and fields: `parse_amount`, `user_id`, `max_retry_count`.
- Avoid abbreviations unless they are universally understood (`ctx`, `err`, `buf`, `len`).

### Types and Traits

- `PascalCase` for types, traits, enums, and type aliases: `UserStore`, `FromStr`, `ParseError`.
- `PascalCase` for enum variants: `TokenKind::LeftParen`, `Error::NotFound`.

### Constants and Statics

- `SCREAMING_SNAKE_CASE` for constants and statics: `MAX_RETRIES`, `DEFAULT_TIMEOUT_MS`.

### Acronyms

Capitalize acronyms as a unit: `HttpClient`, `JsonParser`, `TcpStream`. Do NOT write `HTTPClient` or `JSONParser` — this conflicts with Rust community conventions (contrast with Go).

### Lifetimes

- Single lowercase letter for simple lifetimes: `'a`, `'b`.
- Descriptive names when the lifetime has semantic meaning: `'conn`, `'arena`, `'static`.
- Avoid `'_` (elided lifetime) in positions where the explicit lifetime aids understanding.

## Module Organization

```
src/
  lib.rs              # library crate root; re-exports public API
  main.rs             # binary crate root
  bin/
    server.rs         # additional binaries
  error.rs            # crate-level error types
  config.rs
  store/
    mod.rs            # or store.rs (preferred in Rust 2018+)
    postgres.rs
tests/
  integration_test.rs # integration tests (separate crate, black-box)
benches/
  throughput.rs       # criterion benchmarks
examples/
  basic_usage.rs
```

**Module file style**: Prefer `store.rs` + `store/` directory over `store/mod.rs` for Rust 2018+. The `mod.rs` style is deprecated in favor of the named-file style.

## Doc Comments

Use `///` for item-level documentation (functions, types, modules):

```rust
/// Parses a monetary amount from a string.
///
/// Accepts integers and decimal values with up to 2 decimal places.
/// Returns an error if the input contains non-numeric characters or
/// the value overflows `i64`.
///
/// # Examples
///
/// ```
/// let amount = parse_amount("123.45")?;
/// assert_eq!(amount, 12345);
/// ```
///
/// # Errors
///
/// Returns [`ParseError::InvalidFormat`] if the string is not a valid amount.
pub fn parse_amount(s: &str) -> Result<i64, ParseError> { ... }
```

- `///` for items (functions, structs, enums, traits, modules).
- `//!` for crate/module-level documentation at the top of `lib.rs` or `mod.rs`.
- Include `# Examples`, `# Errors`, `# Panics` sections as appropriate.
- Examples in doc comments are compiled and run as tests (`cargo test --doc`).

## Formatting and Layout

- **`cargo fmt` handles all formatting** — tabs, alignment, blank lines. Do not fight it.
- **Line length**: 100 characters (rustfmt default). Configure in `rustfmt.toml` if your project differs.
- **Trailing commas**: `cargo fmt` adds trailing commas in multi-line expressions — this is idiomatic.
- **`use` declarations**: Group by origin — stdlib, external crates, local crates — with blank lines between groups. `cargo fmt` sorts within groups.

## Prelude and Use Declarations

```rust
use std::collections::HashMap;
use std::io::{self, Write};

use serde::{Deserialize, Serialize};
use tokio::sync::mpsc;

use crate::error::AppError;
use crate::store::UserStore;
```

- Use `use crate::` for local imports — not `super::` unless in nested modules where it is clearer.
- Avoid glob imports (`use module::*`) except in test modules where `use super::*` is conventional.
- Prefer `use std::io::{self, Write}` over two separate use statements.

## Visibility

- Default to private (no `pub`) — only expose what callers need.
- `pub(crate)` for items used across modules within the same crate but not externally.
- `pub(super)` for items exposed only to the parent module.
- Minimize the public API surface of library crates — every public item is a commitment.

## Type Aliases

Use type aliases to reduce repetition in complex types:

```rust
type Result<T> = std::result::Result<T, AppError>;
type SharedState = Arc<Mutex<State>>;
```

Document type aliases when the meaning is not obvious from the name.

## Derive Order Convention

Keep derived traits in a consistent order:

```rust
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct UserId(u64);
```

Conventional order: `Debug`, `Clone`, `Copy`, `PartialEq`, `Eq`, `PartialOrd`, `Ord`, `Hash`, `Default`, then serde/other external traits.
