# Go Patterns

Idiomatic Go patterns for common design problems. Prefer these over ad-hoc solutions.

## Functional Options

Use the functional options pattern for constructors with optional configuration — avoids config structs with dozens of zero values and enables forward-compatible APIs:

```go
type Server struct {
    addr    string
    timeout time.Duration
    maxConn int
}

type Option func(*Server)

func WithTimeout(d time.Duration) Option {
    return func(s *Server) { s.timeout = d }
}

func WithMaxConn(n int) Option {
    return func(s *Server) { s.maxConn = n }
}

func NewServer(addr string, opts ...Option) *Server {
    s := &Server{addr: addr, timeout: 30 * time.Second, maxConn: 100}
    for _, opt := range opts {
        opt(s)
    }
    return s
}

// Usage:
srv := NewServer(":8080", WithTimeout(10*time.Second), WithMaxConn(500))
```

- Provides sensible defaults without requiring callers to specify everything.
- Adding new options is backward-compatible — existing call sites don't break.
- Alternative: a `Config` struct with exported fields if the option count is small and all fields are commonly set.

## Small Interfaces

Prefer single-method or small interfaces — they're composable and easy to mock:

```go
type Reader interface {
    Read(p []byte) (n int, err error)
}

type Writer interface {
    Write(p []byte) (n int, err error)
}

type ReadWriter interface {
    Reader
    Writer
}
```

- Define interfaces where they are **used**, not where they are **implemented**.
- Accept the smallest interface that satisfies your function's needs.
- Return concrete types from constructors so callers can access the full API; let the caller decide what interface to store it as.

## `sync.Once` for Lazy Initialization

Use `sync.Once` for expensive one-time initialization that is safe for concurrent callers:

```go
type Registry struct {
    once    sync.Once
    schemas map[string]Schema
}

func (r *Registry) Schemas() map[string]Schema {
    r.once.Do(func() {
        r.schemas = loadSchemasFromDisk()
    })
    return r.schemas
}
```

- `sync.Once` guarantees `Do` runs exactly once even if called from multiple goroutines simultaneously.
- The zero value of `sync.Once` is ready to use — no initialization needed.
- Do NOT copy a `sync.Once` after first use.

## Context Cancellation and Cleanup

Always derive child contexts and defer cancellation:

```go
func processJob(ctx context.Context, job Job) error {
    ctx, cancel := context.WithTimeout(ctx, 5*time.Minute)
    defer cancel()

    resultCh := make(chan Result, 1)
    go func() {
        resultCh <- doWork(ctx, job)
    }()

    select {
    case result := <-resultCh:
        return result.Err
    case <-ctx.Done():
        return fmt.Errorf("job timed out: %w", ctx.Err())
    }
}
```

- `defer cancel()` immediately after `WithTimeout`/`WithCancel` — no exceptions.
- `select` on both the result channel and `ctx.Done()` to respect cancellation.

## `errgroup` for Parallel Work

Use `golang.org/x/sync/errgroup` for parallel tasks where you want the first error and clean cancellation:

```go
import "golang.org/x/sync/errgroup"

func fetchAll(ctx context.Context, urls []string) ([][]byte, error) {
    g, ctx := errgroup.WithContext(ctx)
    results := make([][]byte, len(urls))

    for i, url := range urls {
        i, url := i, url // capture for Go <1.22
        g.Go(func() error {
            data, err := fetch(ctx, url)
            if err != nil {
                return fmt.Errorf("fetching %s: %w", url, err)
            }
            results[i] = data
            return nil
        })
    }

    if err := g.Wait(); err != nil {
        return nil, err
    }
    return results, nil
}
```

- `errgroup.WithContext` returns a derived context that is cancelled when the first goroutine returns an error.
- `g.Wait()` blocks until all goroutines finish and returns the first non-nil error.

## `io.Writer` for Dependency Injection

Accept `io.Writer` instead of concrete types like `*os.File` or `*bytes.Buffer` — makes functions testable and composable:

```go
// Instead of writing to stdout directly:
func PrintReport(w io.Writer, report Report) error {
    return template.Execute(w, report)
}

// In production:
PrintReport(os.Stdout, report)

// In tests:
var buf bytes.Buffer
PrintReport(&buf, report)
assert.Contains(t, buf.String(), "expected text")
```

## Embedding Over Inheritance

Use struct embedding to compose behavior rather than inheritance hierarchies:

```go
type Base struct {
    logger *slog.Logger
    db     *sql.DB
}

func (b *Base) logError(msg string, err error) {
    b.logger.Error(msg, "error", err)
}

type UserService struct {
    Base
    cache *redis.Client
}

func (u *UserService) GetUser(ctx context.Context, id string) (*User, error) {
    user, err := queryUser(ctx, u.db, id)
    if err != nil {
        u.logError("get user failed", err)  // promoted from Base
        return nil, err
    }
    return user, nil
}
```

- Embedding promotes fields and methods from the embedded type.
- Prefer embedding over direct delegation when the embedded type's full interface should be visible.
- Do NOT embed types just to avoid writing a few forwarding methods — only embed when the "is-a" relationship makes semantic sense.

## `_` Imports for Side Effects

Blank imports for side-effect registration must always have an explanatory comment:

```go
import (
    _ "github.com/lib/pq"           // register PostgreSQL driver
    _ "image/png"                   // register PNG decoder
    _ "net/http/pprof"              // register pprof HTTP handlers
)
```

Without a comment, blank imports look like mistakes during review.

## Error Sentinel Values vs Error Types

Choose based on whether callers need to branch on the error:

```go
// Sentinel: caller checks with errors.Is
var ErrNotFound = errors.New("not found")

// Typed error: caller checks with errors.As to access fields
type ValidationError struct {
    Field   string
    Message string
}
func (e *ValidationError) Error() string {
    return fmt.Sprintf("validation error on %s: %s", e.Field, e.Message)
}

// Usage:
if errors.Is(err, ErrNotFound) { ... }

var valErr *ValidationError
if errors.As(err, &valErr) {
    fmt.Println(valErr.Field)
}
```

- Use sentinel errors for fixed, well-known conditions (`ErrNotFound`, `io.EOF`).
- Use typed errors when callers need additional context (field names, status codes, retry-after).
- Wrap both with `%w` so the error chain is preserved through layers.

## Channel-Based Worker Pool

Cap concurrency with a buffered channel as a semaphore:

```go
func processItems(ctx context.Context, items []Item, concurrency int) error {
    sem := make(chan struct{}, concurrency)
    g, ctx := errgroup.WithContext(ctx)

    for _, item := range items {
        item := item
        sem <- struct{}{}
        g.Go(func() error {
            defer func() { <-sem }()
            return process(ctx, item)
        })
    }
    return g.Wait()
}
```

- The buffered channel blocks at capacity, naturally throttling concurrent goroutines.
- `defer func() { <-sem }()` ensures the slot is released even on error.
