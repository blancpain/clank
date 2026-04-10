# Rust Testing

Use Rust's built-in `#[test]` framework as the foundation. These rules cover unit tests, integration tests, property testing, benchmarks, and doctests.

## Unit Tests in the Same File

Place unit tests in a `#[cfg(test)] mod tests` block at the bottom of each source file:

```rust
pub fn add(a: i32, b: i32) -> i32 {
    a + b
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn add_positive_numbers() {
        assert_eq!(add(2, 3), 5);
    }

    #[test]
    fn add_negative_numbers() {
        assert_eq!(add(-1, -2), -3);
    }
}
```

- `use super::*` gives access to the module's unexported items — this is the Go-equivalent of white-box testing.
- Name tests as statements: `parses_valid_amount`, `rejects_empty_string`, `returns_error_on_overflow`.

## Integration Tests

Integration tests live in the `tests/` directory and are compiled as separate crates — they only have access to the public API:

```
tests/
  api_roundtrip.rs
  store_integration.rs
```

```rust
use mylib::Store;

#[test]
fn store_insert_and_retrieve() {
    let store = Store::new();
    store.insert("key", "value");
    assert_eq!(store.get("key"), Some("value"));
}
```

Run: `cargo test --test store_integration`

## `#[should_panic]`

Test that code panics under known-invalid conditions:

```rust
#[test]
#[should_panic(expected = "index out of bounds")]
fn panics_on_invalid_index() {
    let v = vec![1, 2, 3];
    let _ = v[10];
}
```

The `expected` parameter matches a substring of the panic message — use it to guard against false positives from unrelated panics.

## Async Tests with Tokio

For async code, use `#[tokio::test]`:

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn fetch_returns_data() {
        let client = Client::new();
        let result = client.fetch("https://example.com").await;
        assert!(result.is_ok());
    }
}
```

- `#[tokio::test]` creates a single-threaded Tokio runtime by default.
- Use `#[tokio::test(flavor = "multi_thread")]` for tests that require the multi-threaded scheduler.

## Property Testing

Use `proptest` or `quickcheck` for property-based testing — especially useful for parsers, serializers, and pure functions:

```rust
use proptest::prelude::*;

proptest! {
    #[test]
    fn roundtrip_encode_decode(s in "\\PC*") {
        let encoded = encode(&s);
        let decoded = decode(&encoded).unwrap();
        prop_assert_eq!(s, decoded);
    }

    #[test]
    fn parse_amount_never_panics(s in ".*") {
        let _ = parse_amount(&s);  // must not panic
    }
}
```

- `proptest!` generates random inputs and shrinks failures to minimal examples.
- Use `prop_assert_eq!` and `prop_assert!` (not `assert!`) inside `proptest!` blocks — they return `Err` on failure rather than panicking, enabling shrinking.

## Benchmarks with Criterion

Use `criterion` for reliable benchmarks:

```toml
[dev-dependencies]
criterion = { version = "0.5", features = ["html_reports"] }

[[bench]]
name = "throughput"
harness = false
```

```rust
use criterion::{black_box, criterion_group, criterion_main, Criterion};

fn bench_parse(c: &mut Criterion) {
    c.bench_function("parse_amount 12345", |b| {
        b.iter(|| parse_amount(black_box("12345")))
    });
}

criterion_group!(benches, bench_parse);
criterion_main!(benches);
```

- `black_box()` prevents the compiler from optimizing away the computation being benchmarked.
- Run: `cargo bench`
- Commit benchmark baselines to `target/criterion/` for regression tracking (or use `cargo-criterion`).

## Doctests

Examples in doc comments are compiled and run as tests:

```rust
/// Parses a monetary amount in cents.
///
/// # Examples
///
/// ```
/// use mylib::parse_amount;
///
/// let cents = parse_amount("12.34").unwrap();
/// assert_eq!(cents, 1234);
/// ```
pub fn parse_amount(s: &str) -> Result<i64, ParseError> { ... }
```

- Run: `cargo test --doc`
- Mark examples that should not run with `no_run`: ` ```rust,no_run`
- Mark examples that are expected to fail with `should_panic`: ` ```rust,should_panic`
- Doctests also serve as documentation — write them to illustrate common usage, not just to achieve test coverage.

## Test Helpers and Fixtures

Extract common test setup into helper functions. Use the `#[allow(dead_code)]` attribute if a helper is only used in tests:

```rust
#[cfg(test)]
mod tests {
    fn make_store() -> Store {
        Store::with_capacity(100)
    }

    #[test]
    fn insert_retrieves_correctly() {
        let store = make_store();
        // ...
    }
}
```

For complex shared state, use a `setup()` function rather than global state — Rust tests run in parallel by default.

## Test Isolation

Rust tests run in parallel by default. Ensure tests do not:

- Write to the same file path without using `tempfile::NamedTempFile` or `tempdir`.
- Depend on global mutable state (`static mut`, `OnceCell` with side effects).
- Assume a specific port is available — bind to port `0` and read the actual assigned address.

Run tests single-threaded when sequential behavior is required:
```bash
cargo test -- --test-threads=1
```

## What NOT to Do

- No `println!` in test bodies for debugging — use `eprintln!` (captured) or `dbg!()` (removed in release).
- No `std::thread::sleep` in tests — use mock time or event-driven waits.
- No `unwrap()` on `Result` in tests where the error message would be unhelpful — use `expect("context")` or `?` with `#[tokio::test]` returning `Result<(), Box<dyn Error>>`.
- Do not use `#[ignore]` as a permanent fix — either fix the test or delete it.
