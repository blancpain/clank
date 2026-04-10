# Rust Security

Security rules for Rust code. Rust's ownership system eliminates whole classes of vulnerabilities, but new attack surfaces exist around `unsafe`, integer semantics, and dependency supply chains.

## `unsafe` Discipline

Every use of `unsafe` is a manual proof obligation — the compiler no longer checks invariants inside unsafe blocks.

### The `// SAFETY:` Comment Requirement

Every `unsafe` block, `unsafe fn`, and `unsafe impl` must have a `// SAFETY:` comment immediately above it:

```rust
// SAFETY: `ptr` is non-null and points to a valid `T` that is properly
// aligned, because it was obtained from `Box::into_raw` and has not been
// freed or aliased since.
let value = unsafe { Box::from_raw(ptr) };
```

Without this comment, `unsafe` code cannot be reviewed for correctness.

### Common Unsafe Pitfalls

- **`mem::transmute`**: Reinterprets raw bytes without type checking. Use `From`/`Into` conversions, `bytemuck::cast` for POD types, or pointer casts instead.
- **Invalid references**: Creating a `&T` or `&mut T` to uninitialized, freed, or misaligned memory causes undefined behavior. Use `MaybeUninit<T>` for uninitialized data.
- **Aliased mutable references**: Rust's aliasing rules forbid two `&mut T` to the same data at the same time. This rule applies even in `unsafe` code — violating it is UB.
- **`unsafe impl Send` / `unsafe impl Sync`**: Only implement these if you can prove the type is safe to transfer/share across threads. Document the proof.
- **Data races**: Accessing shared mutable data from multiple threads without synchronization is undefined behavior, even in `unsafe`. Use `Mutex`, `RwLock`, or `atomic` operations.

## Integer Overflow and Arithmetic

Rust panics on integer overflow in debug builds and wraps silently in release builds. Use explicit arithmetic for security-critical calculations:

```rust
// Silently wraps in release: WRONG for security-critical code
let total = a + b;

// Use checked, saturating, or wrapping explicitly:
let total = a.checked_add(b).ok_or(Error::Overflow)?;  // returns error
let total = a.saturating_add(b);                        // caps at MAX
let total = a.wrapping_add(b);                          // explicit wrap
```

- Use `checked_*` for values that come from untrusted input (HTTP request fields, parsed files).
- Use `saturating_*` for counters where wrapping would be incorrect but panicking is too aggressive.
- Use `wrapping_*` only when the wrap-around is intentional (e.g., hash functions, checksum algorithms).

## Slice Indexing and Bounds Checks

Direct indexing (`slice[i]`) panics on out-of-bounds. Use safe alternatives when the index comes from untrusted input:

```rust
// Panics on out-of-bounds:
let byte = buffer[offset];

// Returns None instead of panicking:
let byte = buffer.get(offset).ok_or(Error::OutOfBounds)?;
```

In `unsafe` code, `get_unchecked` skips bounds checks — only use it after explicitly proving the index is valid, and document the proof in a `// SAFETY:` comment.

## `cargo audit` — Dependency Vulnerability Scanning

Run `cargo audit` in CI to detect known vulnerabilities in dependencies:

```bash
cargo install cargo-audit
cargo audit
```

- Add `cargo audit` as a mandatory CI step alongside `cargo test`.
- Review `cargo audit` findings before adding new dependencies.
- Pin Cargo.lock in binary crates (commit it) so the exact resolved versions are reproducible.

## Dependency Supply Chain

- Prefer dependencies from established, maintained crates (check crates.io download counts, GitHub activity, and last publish date).
- Minimize the dependency tree — each dependency is a trust decision. Use `cargo tree` to understand the full transitive dependency graph.
- Audit new dependencies before merging: read the source if the crate is small, or check for recent suspicious activity.
- Use `[patch]` in `Cargo.toml` only with care — patching a dependency with an unvetted fork introduces supply-chain risk.

## Sensitive Data Handling

Use the `secrecy` crate to prevent secrets from being printed or logged accidentally:

```rust
use secrecy::{ExposeSecret, Secret};

struct Config {
    api_key: Secret<String>,
    database_url: Secret<String>,
}

fn connect(config: &Config) -> Connection {
    let url = config.database_url.expose_secret();
    // use url here; it won't appear in Debug/Display output of Config
}
```

- `Secret<T>` wraps a value so its `Debug` and `Display` implementations show `[REDACTED]`.
- Call `.expose_secret()` only at the point where the value is needed.
- Never log secrets, include them in error messages, or store them in `String` fields in structs that derive `Debug`.

## SQL Injection and Parameterized Queries

Use parameterized queries for all database access — never concatenate user input into SQL:

```rust
// WRONG — SQL injection
let query = format!("SELECT * FROM users WHERE name = '{}'", user_input);
sqlx::query(&query).fetch_all(&pool).await?;

// CORRECT — parameterized via sqlx
let users = sqlx::query_as!(User,
    "SELECT * FROM users WHERE name = $1",
    user_input
)
.fetch_all(&pool)
.await?;
```

- `sqlx` compile-time query checking (`query!`, `query_as!`) verifies SQL syntax and parameter types at compile time.
- For dynamic queries with variable column names, validate column names against an allowlist — never interpolate raw strings as SQL identifiers.

## Deserialization from Untrusted Input

- **Bound input size**: Before deserializing, limit the size of the input buffer. An unbounded deserialization of user-supplied JSON can exhaust memory.
- **`serde_json` with `limit`**: Use a `Read` adapter with a size limit: `serde_json::from_reader(input.take(MAX_BYTES))`.
- **Recursive depth**: Deeply nested JSON/TOML/YAML can cause stack overflows. Check if your deserialization library has a depth limit.
- **Avoid `bincode` / custom binary formats for untrusted input**: Binary formats often lack schema validation, making them harder to audit. Prefer JSON or protobuf with explicit schema validation.

## TLS and Certificate Validation

- Never disable certificate verification (`danger_accept_invalid_certs`, `verify_mode = VerifyNone`). Only acceptable in integration tests against local test servers, with an explicit comment.
- Use the `rustls` crate rather than OpenSSL bindings where possible — it is memory-safe by construction.
- Enforce minimum TLS 1.2. TLS 1.3 is preferred for new services.

## Path Traversal

Validate file paths that originate from user input:

```rust
use std::path::{Path, PathBuf};

fn safe_path(base: &Path, user_input: &str) -> Result<PathBuf, Error> {
    let candidate = base.join(user_input);
    let canonical = candidate.canonicalize()?;
    if !canonical.starts_with(base.canonicalize()?) {
        return Err(Error::PathTraversal);
    }
    Ok(canonical)
}
```

- `canonicalize()` resolves symlinks and `..` components.
- Check `starts_with(base)` after canonicalization — not before.
- Be aware that `canonicalize()` requires the path to exist; for not-yet-created files, validate the parent directory instead.
