# Python Coding Style

Follow these Python-specific conventions in addition to the general coding style guidelines.

## Standards

- Follow **PEP 8** conventions for naming and layout
- Use **type annotations** on all public function signatures
- Use **ruff** for linting and formatting (preferred over black + flake8 separately)
- Use **isort**-compatible import ordering (ruff handles this too)

## Naming

- `snake_case` for functions, variables, modules
- `PascalCase` for classes
- `SCREAMING_SNAKE_CASE` for module-level constants
- `_leading_underscore` for internal/private names (no name mangling unless truly necessary)
- Never shadow builtins: `list`, `dict`, `str`, `type`, `id`, `input`, `map`, `filter`, `set`, `min`, `max`, `sum`

## Immutability

Prefer immutable data structures where possible:

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class Config:
    host: str
    port: int

from typing import NamedTuple

class Point(NamedTuple):
    x: float
    y: float
```

## Type Annotations

Use modern syntax (Python 3.10+):

```python
def process(items: list[str], limit: int | None = None) -> dict[str, int]:
    ...
```

Avoid `Optional[X]` — prefer `X | None`. Avoid `List`, `Dict`, `Tuple` from `typing` — use built-in generics.

## Imports

- Explicit imports only — no `from module import *`
- Group imports: stdlib → third-party → local (blank line between groups)
- Never use relative imports (`from . import`) beyond one level for clarity

## String Formatting

- Use f-strings for interpolation (`f"Hello {name}"`)
- Use `"".join(parts)` not string concatenation in loops (O(n²) otherwise)
- Avoid `%` formatting except in logging (where it's lazy-evaluated)

## Functions

- **No mutable default arguments**: `def f(x=[])` — use `def f(x=None)` and initialize inside
- Keep functions focused: if a function exceeds ~40 lines, consider extracting
- Public functions that aren't obvious from the signature need a docstring
- Use `logging.getLogger(__name__)` in production code, not bare `print()`

## Comprehensions

Prefer comprehensions over verbose loops:

```python
values = [x * 2 for x in items if x > 0]
lookup = {k: v for k, v in pairs}
unique = {x.lower() for x in names}
```

Do NOT use comprehensions with side effects — use a plain `for` loop instead.

## pathlib

Use `pathlib.Path` for all file system operations:

```python
from pathlib import Path

config_file = Path("config") / "settings.toml"
if config_file.exists():
    text = config_file.read_text()
```

Never use `os.path.join()`, `os.path.exists()`, `open("dir/" + name)`.

## Context Managers

All resources (files, connections, locks, temp files) must use `with`:

```python
with open(path) as f:
    data = f.read()

with db.connect() as conn:
    conn.execute(query)
```

## Dependency Management

Prefer **uv** for managing Python environments and dependencies (`uv add`, `uv sync`).
