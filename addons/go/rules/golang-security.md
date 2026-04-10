# Go Security

Security rules for Go code. These complement the general security reviewer and focus on Go-specific attack vectors.

## Cryptography

### Use `crypto/rand`, Not `math/rand`

`math/rand` is a pseudo-random number generator seeded deterministically. Never use it for:

- Tokens, session IDs, API keys
- Password salts
- Nonces or IVs
- CSRF tokens

```go
// WRONG — predictable
import "math/rand"
token := fmt.Sprintf("%d", rand.Int63())

// CORRECT — cryptographically secure
import "crypto/rand"
import "encoding/hex"

b := make([]byte, 32)
if _, err := rand.Read(b); err != nil {
    return fmt.Errorf("generating token: %w", err)
}
token := hex.EncodeToString(b)
```

In Go 1.20+, `math/rand` is auto-seeded, but it is still NOT cryptographically secure.

### TLS Configuration

- Do not disable certificate verification: `tls.Config{InsecureSkipVerify: true}` is a critical security hole. Only acceptable in local dev with a comment.
- Enforce minimum TLS version: `tls.Config{MinVersion: tls.VersionTLS12}`.
- Prefer `tls.VersionTLS13` for new services.

## SQL Injection

Use parameterized queries via `database/sql` — never concatenate user input into SQL strings:

```go
// WRONG — SQL injection
query := fmt.Sprintf("SELECT * FROM users WHERE name = '%s'", userInput)
rows, _ := db.Query(query)

// CORRECT — parameterized
rows, err := db.QueryContext(ctx, "SELECT * FROM users WHERE name = $1", userInput)
```

- Use `$1`, `$2` placeholders for PostgreSQL; `?` for MySQL/SQLite.
- For dynamic queries (variable number of params, dynamic ORDER BY), sanitize column names against an allowlist — never interpolate raw user strings as identifiers.

## Path Traversal

User-controlled file paths must be sanitized before use:

```go
// WRONG — path traversal: userInput = "../../etc/passwd"
path := filepath.Join(baseDir, userInput)

// CORRECT — clean and verify the path stays inside baseDir
cleanPath := filepath.Clean(filepath.Join(baseDir, userInput))
if !strings.HasPrefix(cleanPath, filepath.Clean(baseDir)+string(os.PathSeparator)) {
    return errors.New("path traversal detected")
}
```

## Command Injection

Never construct shell commands from user input with `exec.Command` + `sh -c`:

```go
// WRONG — shell injection
cmd := exec.Command("sh", "-c", "grep "+userInput+" /var/log/app.log")

// CORRECT — pass arguments as separate strings; no shell interpolation
cmd := exec.Command("grep", "--", userInput, "/var/log/app.log")
```

- Prefer variadic `exec.Command("binary", arg1, arg2)` over shell strings.
- Validate and restrict the set of allowed arguments where possible.
- Never pass user-controlled data as the binary name itself.

## Goroutine Leaks as a Security Concern

Goroutine leaks can be exploited for resource exhaustion (denial of service):

- HTTP handlers that launch goroutines without bounded lifetimes — an attacker can trigger many requests and exhaust memory.
- Use `context.WithTimeout` or `context.WithDeadline` on every outbound request to bound its lifetime.
- Use `golang.org/x/sync/semaphore` or a worker pool to cap concurrency.

## `unsafe` Package

Every use of the `unsafe` package requires explicit review:

- `unsafe.Pointer` casts bypass the type system — an incorrect cast causes undefined behavior or memory corruption.
- Every `unsafe` block must have a `// SAFETY:` comment explaining why the invariants hold.
- `unsafe.Slice` and `unsafe.SliceData` (Go 1.17+) are safer than raw pointer arithmetic but still require justification.
- `reflect.SliceHeader` and `reflect.StringHeader` are deprecated in Go 1.20 — use `unsafe.Slice`/`unsafe.SliceData` instead.

```go
// SAFETY: p points to a C-allocated array of n bytes that will remain valid
// for the lifetime of this function call.
b := unsafe.Slice((*byte)(p), n)
```

## `encoding/gob` and `encoding/json` with Untrusted Input

- `encoding/gob` deserializes into arbitrary types based on type metadata — do NOT decode untrusted `gob` streams. Use JSON or protobuf with schema validation instead.
- `encoding/json`: `json.Unmarshal` into `interface{}` converts numbers to `float64` which can lose precision for large integers. Use `json.Decoder` with `UseNumber()` or unmarshal into typed structs.
- Validate and bound input sizes before decoding — an attacker can send gigabyte JSON arrays.

## HTTP Security Headers

For Go HTTP servers, set security headers explicitly (or use a middleware library):

```go
func securityHeaders(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        w.Header().Set("X-Content-Type-Options", "nosniff")
        w.Header().Set("X-Frame-Options", "DENY")
        w.Header().Set("Content-Security-Policy", "default-src 'self'")
        next.ServeHTTP(w, r)
    })
}
```

## Sensitive Data in Logs

- Never log passwords, API keys, tokens, PII, or full request bodies containing credentials.
- Redact sensitive struct fields: implement `String() string` or `MarshalJSON()` to return `[REDACTED]`.
- Use structured logging (`log/slog`, `zap`, `zerolog`) with field-level control rather than `fmt.Sprintf` into log messages — easier to audit and redact.

## Dependency Security

- Run `govulncheck ./...` (Go's official vulnerability scanner) in CI: `go install golang.org/x/vuln/cmd/govulncheck@latest`.
- Pin dependencies in `go.sum` — commits that touch `go.mod` should also commit the updated `go.sum`.
- Audit new dependencies for supply-chain risk before adding them to `go.mod`.
