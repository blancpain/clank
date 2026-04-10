# Go Coding Style

Follow these Go-specific conventions in addition to the general coding style guidelines. Go has strong community conventions enforced by `gofmt` and `golangci-lint` — lean into them.

## Standards

- Run **`gofmt`** (or `goimports`) on every file before committing. No exceptions.
- Use **`golangci-lint`** with a project `.golangci.yml` for consistent lint rules across the team.
- Target **Go 1.21+** unless the project has a specific constraint; note the minimum in `go.mod`.

## Naming

### Packages

- Package names are **all lowercase**, single words, no underscores, no camelCase: `httputil`, `store`, `config`.
- The package name is part of the API — choose names that read well as `package.Symbol`: `http.Client`, not `httputil.HttpClient`.
- Avoid stutter: `store.Store` → rename the type to `store.Client` or `store.DB`.
- Test-only packages use the `_test` suffix on the package name: `package store_test`.

### Exported vs Unexported

- **Exported** (public): PascalCase — `type UserStore struct`, `func NewUserStore(...)`.
- **Unexported** (private): camelCase — `type userStore struct`, `func newUserStore(...)`.
- Use unexported identifiers for implementation details; export only what callers need.

### Functions and Methods

- **Function names**: verb or verb-noun — `Get`, `Parse`, `NewClient`, `RunServer`.
- **Getter methods**: `Name()` not `GetName()`. Go convention omits the `Get` prefix.
- **Setter methods**: `SetName(name string)` — `Set` prefix is conventional for setters.
- **Receiver names**: 1-2 character abbreviation of the type name, consistent across all methods. `func (c *Client) Do(...)`, not `func (client *Client) Do(...)` or `func (self *Client) Do(...)`. Never use `self` or `this`.
- **Boolean functions**: use `Is`, `Has`, `Can`, `Should` prefix — `IsEmpty()`, `HasChildren()`.

### Variables and Constants

- **Variables**: camelCase, short in small scopes. Single-letter loop vars (`i`, `v`, `k`) are idiomatic.
- **Constants**: camelCase for unexported (`maxRetries`), PascalCase for exported (`MaxRetries`). Avoid `SCREAMING_CASE` — that's C, not Go.
- **Acronyms**: capitalize consistently — `userID` not `userId`, `parseURL` not `parseUrl`, `HTTPClient` not `HttpClient`.

## File Organization

```
myrepo/
  cmd/
    myserver/
      main.go          # binary entry point
  internal/
    store/
      store.go         # package store — core types and interface
      store_test.go
      postgres.go      # postgres implementation
  pkg/
    httpmiddleware/    # shared, importable by external consumers
  go.mod
  go.sum
```

- `cmd/` — binary entry points. Each subdirectory = one binary.
- `internal/` — packages not importable by external modules (enforced by the Go toolchain).
- `pkg/` — packages intended for external consumption (optional convention).
- Avoid a flat `main.go` at repo root for multi-package projects.

## Error Messages

- **Lowercase, no trailing punctuation**: `"failed to connect to database"` not `"Failed to connect to database."`.
- **Wrap with context**: `fmt.Errorf("loading config: %w", err)` — callers read from outermost to inner.
- **No redundancy**: `"error: failed to read file"` — drop `"error:"` prefix since the variable is already an error.

## Formatting and Layout

- **`gofmt` handles indentation** (tabs, not spaces) and alignment — do not fight it.
- **Line length**: No hard limit in the spec, but aim for <100 characters for readability. Long lines are fine for URLs in comments.
- **Blank lines**: One blank line between top-level declarations. Use blank lines inside functions to separate logical sections, but keep functions short enough that excessive blank lines signal a refactor opportunity.
- **Comment style**: `//` for single-line, `/* */` for multi-line (rare). Doc comments (`// Symbol ...`) immediately precede the declaration with no blank line between comment and declaration.
- **Doc comments**: All exported identifiers need a doc comment starting with the identifier name: `// Client manages HTTP connections to the backend.`

## Imports

```go
import (
    "context"         // stdlib first
    "fmt"
    "net/http"

    "github.com/org/lib" // third-party second (blank line separator)

    "myrepo/internal/store" // local last
)
```

- Use `goimports` to manage grouping automatically.
- Alias imports only when there is a genuine name collision — avoid cosmetic aliases.
- Blank imports (`import _ "pkg"`) for side effects (e.g., driver registration) must have a comment explaining why.

## Short Variable Declarations

- Prefer `:=` inside function bodies. Use `var` at package level and for zero-value initialization when the type is important to make explicit:
  ```go
  var wg sync.WaitGroup
  var result []string
  ```
- Avoid redundant type declarations: `var s string = ""` → `s := ""`.
