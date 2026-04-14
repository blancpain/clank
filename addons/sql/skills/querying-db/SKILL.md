---
name: querying-db
description: Use when running SQL queries, database lookups, or Python scripts that touch a SQL database — enforces reading the schema reference first, using the postgres MCP when available, and avoiding common pitfalls.
---

# Querying the Database

## Step 1: Read the Schema

**Before writing ANY query**, read `.claude/skills/querying-db/schema.txt` (project root). It has every table, column, enum value, and join pattern. One read replaces multiple failed attempts.

If `schema.txt` does not exist, see `schema.txt.template` in this skill directory for the expected format. Fill it in and rename it to `schema.txt` before proceeding.

**Keeping schema.txt in sync:** this skill pairs with the `schema-sync-reminder` hook (installed by the sql preset). When a schema source file is edited (`schema.py`, `schema.sql`, migrations, Prisma schema, etc.), the hook blocks with a reminder to update `schema.txt` in the same turn. If you add a new table or column, update both the source and this reference together — stale references cause queries to fail silently.

## Step 2: Execute

**Prefer the `mcp__postgres__query` tool** (connects via the PostgreSQL MCP server configured in `.mcp.json`). Pass SQL directly — no Python, no Bash, no SSH needed.

```
mcp__postgres__query(sql="SELECT COUNT(*) FROM users")
```

**Fallback (only if MCP tool is not in your tool list):** find the project's DB connection helper and use it from a Python script.

```bash
rg 'get_connection|create_engine|DB_URL' --type py -l
```

Then use the helper:

```python
from database.schema import get_connection
conn = get_connection()
cur = conn.cursor()
cur.execute("YOUR SQL HERE")
for r in cur.fetchall(): print(r)
conn.close()
```

Never use bare `python3` or `python` without the project venv if one exists. Check for `.venv/bin/python` or `venv/bin/python` first.

## Gotchas

- **Timezone handling**: `timestamptz` columns store UTC and convert to session timezone on read. Bare `timestamp` ignores timezone entirely. Always use `timestamptz` for production data. Filter with explicit timezone: `WHERE created_at >= '2024-01-01'::timestamptz`.

- **Float vs integer casts**: Joining on numeric columns, watch for `.0` suffix issues. If a column is stored as `FLOAT`, casting to text produces `'123.0'` not `'123'`. Always cast via `float::bigint::text` (SQL) or `str(int(val))` (Python), never `str(float_val)` directly.

- **JSONB vs JSON**: `JSONB` is indexed and supports `@>`, `?`, and GIN indexes. `JSON` preserves insertion order but is slower for lookups. Prefer `JSONB`.

- **Parameter binding**: Use `$1`/`$2` for parameterized queries in psycopg2 (`%s`) or asyncpg (`$1`). Never concatenate user input into SQL strings.

- **NULL semantics**: Use `IS NULL` / `IS NOT NULL`, not `= NULL`. Use `NOT EXISTS` instead of `NOT IN` when the subquery may contain NULLs — `NOT IN (NULL, ...)` always returns false.

- **Quoted identifiers**: Column names that are camelCase or contain special characters must be double-quoted: `SELECT "gameId" FROM ...`. Check `schema.txt` for columns that require quoting.
