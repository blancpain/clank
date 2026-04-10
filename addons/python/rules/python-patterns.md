# Python Patterns

Idiomatic Python patterns for maintainable, production-grade code.

## Context Managers

Use `with` for all resource management:

```python
with open(path, "r") as f:
    data = f.read()

with db.connect() as conn, conn.cursor() as cur:
    cur.execute("SELECT 1")
```

Implement `__enter__`/`__exit__` for custom resources, or use `@contextlib.contextmanager`:

```python
from contextlib import contextmanager

@contextmanager
def timer(label: str):
    import time
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        print(f"{label}: {elapsed:.3f}s")

with timer("data load"):
    load_data()
```

## Dataclasses

Use `@dataclass` for plain data containers instead of dicts or namedtuples where mutability is needed:

```python
from dataclasses import dataclass, field

@dataclass
class JobConfig:
    host: str
    port: int
    retries: int = 3
    tags: list[str] = field(default_factory=list)  # mutable default via field()

@dataclass(frozen=True)
class GameId:
    season: int
    game_number: int
```

Use `frozen=True` for value objects that should not be mutated after construction.

## Enum

Use `Enum` (or `StrEnum` in Python 3.11+) for sets of named constants — never bare strings or magic numbers:

```python
from enum import Enum, auto

class Status(Enum):
    PENDING = auto()
    RUNNING = auto()
    DONE = auto()
    FAILED = auto()

def handle(status: Status) -> None:
    match status:
        case Status.DONE:
            ...
        case Status.FAILED:
            ...
```

`StrEnum` for cases where the string value matters (e.g., DB columns, API responses):

```python
from enum import StrEnum

class Bookmaker(StrEnum):
    PINNACLE = "pinnacle"
    FANDUEL = "fanduel"
```

## Protocol (Duck Typing)

Prefer `Protocol` over `ABC` for structural interfaces — it doesn't require inheritance:

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class Fetcher(Protocol):
    def fetch(self, url: str) -> bytes: ...
    def close(self) -> None: ...

def download(fetcher: Fetcher, url: str) -> bytes:
    try:
        return fetcher.fetch(url)
    finally:
        fetcher.close()
```

## Generators

Use generators for lazy, memory-efficient iteration:

```python
def read_chunks(path: str, chunk_size: int = 4096):
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            yield chunk

for chunk in read_chunks("large_file.bin"):
    process(chunk)
```

Use `yield from` to delegate to sub-generators:

```python
def flatten(nested):
    for item in nested:
        if isinstance(item, list):
            yield from flatten(item)
        else:
            yield item
```

## TypedDict

Use `TypedDict` for typed dict-shaped data (API responses, config dicts):

```python
from typing import TypedDict

class GameEvent(TypedDict):
    event_id: int
    event_type: str
    period: int
    time_in_period: str

def parse_event(raw: dict) -> GameEvent:
    return GameEvent(
        event_id=raw["eventId"],
        event_type=raw["typeDescKey"],
        period=raw["periodDescriptor"]["number"],
        time_in_period=raw["timeInPeriod"],
    )
```

## Match Statements (3.10+)

Use structural pattern matching for complex dispatch:

```python
match event["type"]:
    case "goal":
        handle_goal(event)
    case "penalty":
        handle_penalty(event)
    case "shot-on-goal" if event["period"] == 5:
        handle_shootout_save(event)
    case _:
        pass
```

## `__slots__`

Add `__slots__` to classes that are instantiated thousands of times to reduce memory:

```python
class PlayerStat:
    __slots__ = ("player_id", "goals", "assists")

    def __init__(self, player_id: int, goals: int, assists: int):
        self.player_id = player_id
        self.goals = goals
        self.assists = assists
```

## Functools

```python
from functools import lru_cache, cached_property, partial

@lru_cache(maxsize=256)
def expensive_lookup(key: str) -> int:
    ...

class Report:
    @cached_property
    def summary(self) -> str:
        return self._compute_summary()  # computed once, cached as attribute
```

## Exception Chaining

When re-raising or wrapping exceptions, preserve the original cause:

```python
try:
    result = parse(raw)
except ValueError as e:
    raise DataProcessingError(f"Failed to parse record: {raw!r}") from e
```

`from e` attaches the original traceback — critical for debugging production failures.

## Logging

```python
import logging

logger = logging.getLogger(__name__)

logger.debug("Processing %d records", len(records))    # lazy formatting
logger.info("Sync complete: %s rows upserted", count)
logger.exception("Unexpected error during scrape")     # logs current exception with traceback
```

Use `logger.exception()` inside `except` blocks — it automatically includes the traceback. Never use `print()` in production code.
