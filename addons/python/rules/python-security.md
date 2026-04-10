# Python Security

Python-specific security rules extending the general security guidelines.

## Secret Management

Never hardcode secrets. Load from environment variables:

```python
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.environ["OPENAI_API_KEY"]  # raises KeyError if missing — good
db_url = os.environ.get("DB_URL", "")   # returns empty string if missing
```

Use `os.environ["KEY"]` (raises on missing) rather than `os.getenv("KEY")` (silently returns `None`) for required secrets.

## Dangerous Built-ins

**Never use on untrusted input:**

```python
eval(user_input)                  # arbitrary code execution
exec(user_input)                  # arbitrary code execution
compile(user_input, "<string>", "exec")  # same
__import__(user_input)            # arbitrary module load
```

If you need dynamic evaluation, use `ast.literal_eval()` for safe Python literal parsing (strings, numbers, lists, dicts, booleans, None only).

## Deserialization

```python
import pickle
pickle.load(untrusted_file)       # arbitrary code execution — NEVER on untrusted data

import yaml
yaml.load(data)                   # dangerous — use yaml.safe_load(data)
yaml.load(data, Loader=yaml.FullLoader)  # still dangerous for untrusted data

import marshal
marshal.loads(untrusted_bytes)    # arbitrary code execution
```

Safe alternatives: `json`, `tomllib`, `yaml.safe_load()`, `msgpack` with schema validation.

## SQL Injection

Always use parameterized queries — never f-strings or concatenation:

```python
cur.execute(f"SELECT * FROM users WHERE name = '{name}'")  # VULNERABLE

cur.execute("SELECT * FROM users WHERE name = %s", (name,))  # safe
cur.execute("SELECT * FROM users WHERE name = ?", (name,))   # sqlite
```

With ORMs: use the ORM's parameter binding — don't build raw SQL strings.

## Subprocess

```python
import subprocess

subprocess.run(f"ls {user_path}", shell=True)   # command injection if user controls user_path

subprocess.run(["ls", user_path], shell=False)  # safe — list args, no shell interpretation
```

Never use `shell=True` with any user-controlled input. If you must use `shell=True`, validate and sanitize input with an allowlist.

## Path Traversal

Validate file paths before use:

```python
import os
from pathlib import Path

BASE_DIR = Path("/safe/base/dir").resolve()

def safe_open(user_filename: str) -> Path:
    target = (BASE_DIR / user_filename).resolve()
    if not str(target).startswith(str(BASE_DIR)):
        raise ValueError("path traversal detected")
    return target
```

Never use `..` components from user input without resolving and validating against the intended root.

## Timing-Safe Comparison

For secret/token comparison, use `hmac.compare_digest()` to prevent timing attacks:

```python
import hmac

def verify_token(provided: str, expected: str) -> bool:
    return hmac.compare_digest(provided.encode(), expected.encode())
```

Never use `provided == expected` for security-sensitive comparisons.

## Cryptography

- Do NOT use `hashlib.md5()` or `hashlib.sha1()` for security purposes (passwords, signatures, HMAC) — they are broken
- Fine for: checksums, cache keys, non-security deduplication
- Use `hashlib.sha256()` or better for security, `bcrypt`/`argon2` for passwords
- Use `secrets` module (not `random`) for cryptographic tokens: `secrets.token_urlsafe(32)`

## Logging Sensitive Data

Never log secrets, tokens, passwords, or full connection strings:

```python
logging.info(f"Connecting with key={api_key}")   # BAD — key in logs

logging.info("Connecting to API")                 # GOOD — no secret
logging.debug("Request headers: %s", {k: v for k, v in headers.items() if k != "Authorization"})
```

## Security Scanning

Run **bandit** for static security analysis:

```bash
bandit -r src/ -ll   # report medium and above
```

Integrate into CI. Review and suppress findings with `# nosec` comments only when you have verified they are false positives — document why.

## Dependency Safety

- Pin dependencies with lockfiles (`uv.lock`, `pip-compile` outputs)
- Audit dependencies with `pip-audit` or `uv audit`
- Review transitive dependencies for known CVEs before adding new packages
