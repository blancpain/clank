# Python Testing

Use **pytest** as the testing framework. These rules extend the general testing guidelines with Python-specific patterns.

## File Layout

```
src/
  mypackage/
    core.py
tests/
  conftest.py          # shared fixtures
  test_core.py
  test_integration.py
```

Mirror the source structure under `tests/`. Name test files `test_<module>.py`.

## Parametrize Over Duplication

When three or more test functions test variations of the same logic, use `@pytest.mark.parametrize`:

```python
import pytest

@pytest.mark.parametrize("value,expected", [
    (0, "zero"),
    (1, "positive"),
    (-1, "negative"),
])
def test_classify(value, expected):
    assert classify(value) == expected
```

This keeps failure output clear (each case is a separate test ID) while eliminating boilerplate.

## Fixtures

Use **pytest fixtures** for shared setup:

```python
import pytest

@pytest.fixture
def user():
    return User(name="Alice", email="alice@example.com")

def test_greet(user):
    assert greet(user) == "Hello Alice"
```

Extract fixtures used across multiple test files into `conftest.py`.

## Temporary Files — `tmp_path`

Use the built-in `tmp_path` fixture for temporary file I/O:

```python
def test_write_config(tmp_path):
    config = tmp_path / "config.toml"
    write_config(config, {"key": "value"})
    assert config.read_text() == '[key]\nvalue = "value"\n'
```

Never use hardcoded `/tmp/` paths or `tempfile.mkdtemp()` (which leaks between tests).

## Monkeypatching

Use `monkeypatch` to patch environment variables, module attributes, or functions:

```python
def test_uses_env_var(monkeypatch):
    monkeypatch.setenv("API_KEY", "test-key")
    assert get_api_key() == "test-key"

def test_mocked_fetch(monkeypatch):
    monkeypatch.setattr("mypackage.client.requests.get", lambda *a, **k: MockResponse())
    result = fetch_data()
    assert result is not None
```

Prefer `monkeypatch` over `unittest.mock.patch` — it auto-reverts after the test.

## Marks

Mark tests that are slow or require external resources:

```python
@pytest.mark.slow
def test_full_pipeline():
    ...

@pytest.mark.integration
def test_database_round_trip():
    ...

@pytest.mark.network
def test_api_response():
    ...
```

Register marks in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
markers = [
    "slow: marks tests as slow (deselect with '-m not slow')",
    "integration: requires external services",
    "network: makes real network calls",
]
```

Run fast tests only: `pytest -m "not slow and not network"`.

## Coverage

```bash
pytest --cov=src --cov-report=term-missing
```

Aim for >80% coverage on core business logic. Don't chase 100% — test behaviour, not implementation.

## Assert Messages

Add context to assertions so failures are self-diagnosing:

```python
assert result == expected, f"got {result!r}, expected {expected!r} for input {input!r}"
```

## Test Isolation

Each test must be independently runnable:

- No test should depend on another test's side effects
- Reset module globals in teardown or use fixtures that scope properly
- Use `scope="function"` (default) unless you have a strong reason for broader scope

## What NOT to Do

- No `print()` in test bodies — use `capsys` fixture or structured logging
- No `time.sleep()` — use mock clocks (`freezegun`, `pytest-freezegun`) or event-driven waits
- No hardcoded ports or paths — use ephemeral resources via fixtures
