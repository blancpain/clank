# Go Testing

Use Go's built-in `testing` package as the foundation. These rules cover table-driven tests, parallelism, golden files, and benchmarks.

## Table-Driven Tests

Table-driven tests are the idiomatic Go way to test multiple input/output combinations with a single test function:

```go
func TestParseAmount(t *testing.T) {
    tests := []struct {
        name    string
        input   string
        want    int
        wantErr bool
    }{
        {"positive integer", "42", 42, false},
        {"zero", "0", 0, false},
        {"negative", "-1", 0, true},
        {"non-numeric", "abc", 0, true},
    }

    for _, tc := range tests {
        t.Run(tc.name, func(t *testing.T) {
            got, err := ParseAmount(tc.input)
            if (err != nil) != tc.wantErr {
                t.Errorf("ParseAmount(%q) error = %v, wantErr %v", tc.input, err, tc.wantErr)
                return
            }
            if got != tc.want {
                t.Errorf("ParseAmount(%q) = %v, want %v", tc.input, got, tc.want)
            }
        })
    }
}
```

- Name the slice field `tests` or `cases` consistently.
- Always use `t.Run(tc.name, ...)` for subtests — each case gets its own name in test output.
- Include a `name` field that describes the scenario, not just the input.

## `t.Parallel()`

Mark independent tests and subtests as parallel to speed up the test suite:

```go
func TestFoo(t *testing.T) {
    t.Parallel()
    // ...
}

// Inside table-driven tests:
for _, tc := range tests {
    tc := tc // capture range variable (required in Go <1.22)
    t.Run(tc.name, func(t *testing.T) {
        t.Parallel()
        // ...
    })
}
```

- Do NOT call `t.Parallel()` for tests that share mutable global state or depend on external resources (DB, ports) without isolation.
- In Go 1.22+, the `tc := tc` capture is no longer needed — but it doesn't hurt.

## Subtests with `t.Run`

Subtests isolate failures and allow `-run` filtering:

```go
func TestUserService(t *testing.T) {
    t.Run("create", func(t *testing.T) { ... })
    t.Run("delete", func(t *testing.T) { ... })
    t.Run("list", func(t *testing.T) { ... })
}
```

Run a specific subtest: `go test -run TestUserService/create`.

## Golden Files

For large expected outputs (JSON, HTML, generated code), use golden files in `testdata/`:

```go
func TestRenderTemplate(t *testing.T) {
    got := renderTemplate(inputData)

    goldenPath := filepath.Join("testdata", "render_template.golden")
    if *update {
        os.WriteFile(goldenPath, []byte(got), 0644)
        return
    }
    want, err := os.ReadFile(goldenPath)
    if err != nil {
        t.Fatalf("reading golden file: %v", err)
    }
    if got != string(want) {
        t.Errorf("output mismatch:\ngot:  %q\nwant: %q", got, string(want))
    }
}

var update = flag.Bool("update", false, "update golden files")
```

Update golden files: `go test ./... -update`. Commit the updated `.golden` files.

## `testify` vs Stdlib

The standard `testing` package is sufficient for most tests. `testify` (`github.com/stretchr/testify`) is acceptable but not required:

```go
// stdlib — explicit and readable
if got != want {
    t.Errorf("got %v, want %v", got, want)
}

// testify — less boilerplate for equality checks
assert.Equal(t, want, got)
require.NoError(t, err) // stops test on failure (like t.Fatal)
```

- Prefer `require` (fatal) over `assert` (non-fatal) when subsequent assertions depend on the current one passing.
- Don't mix `testify` and raw `t.Fatal`/`t.Error` calls in the same file without reason.

## Benchmarks

Use `testing.B` for performance-sensitive code:

```go
func BenchmarkParseAmount(b *testing.B) {
    for b.Loop() {  // Go 1.24+; use b.N loop for older versions
        ParseAmount("12345")
    }
}

// For setup that shouldn't be measured:
func BenchmarkLargeSort(b *testing.B) {
    data := generateLargeSlice(10000)
    b.ResetTimer()
    for i := 0; i < b.N; i++ {
        sort.Ints(data)
    }
}
```

Run benchmarks: `go test -bench=. -benchmem ./...`

- Always use `b.ResetTimer()` after expensive setup.
- Use `-benchmem` to see allocation counts — zero-allocation hot paths are a common Go optimization goal.

## Fuzz Tests (Go 1.18+)

For input parsing and validation, add fuzz targets:

```go
func FuzzParseAmount(f *testing.F) {
    f.Add("0")
    f.Add("42")
    f.Add("-1")
    f.Fuzz(func(t *testing.T, s string) {
        result, err := ParseAmount(s)
        if err == nil && result < 0 {
            t.Errorf("ParseAmount(%q) returned negative result %d without error", s, result)
        }
    })
}
```

Run: `go test -fuzz=FuzzParseAmount -fuzztime=30s`

- Seed the corpus with known edge cases using `f.Add(...)`.
- Fuzz tests live in the same `_test.go` files as regular tests.

## Test File Layout

```
pkg/
  store/
    store.go
    store_test.go        # package store (white-box — can access unexported)
    store_external_test.go  # package store_test (black-box — public API only)
  testdata/
    fixture.json
    render_output.golden
```

- White-box tests (`package store`) can test unexported functions.
- Black-box tests (`package store_test`) test only the public API — prefer these for consumer-facing behavior.
- Place test fixtures and golden files under `testdata/` (the Go toolchain ignores this directory in builds).

## `t.Helper()`

Mark test helper functions so failures point to the call site, not inside the helper:

```go
func assertNoError(t *testing.T, err error) {
    t.Helper()
    if err != nil {
        t.Fatalf("unexpected error: %v", err)
    }
}
```

## What NOT to Do

- No `time.Sleep` in tests — use channels, `sync.WaitGroup`, or mock clocks.
- No hardcoded ports — use `:0` and let the OS assign, then read the actual address.
- No `log.Fatal` in test helpers — use `t.Fatal` so the test framework handles cleanup.
- No global state mutations without cleanup in `t.Cleanup(func() { ... })`.
