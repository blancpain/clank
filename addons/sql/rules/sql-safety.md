# SQL Safety

## 1. Destructive DDL Requires Explicit Approval

**NEVER** run `DROP TABLE`, `DROP COLUMN`, `TRUNCATE`, or `DELETE` without a `WHERE` clause unless the user has explicitly said "yes, do it."

- If the user asks for a destructive schema change (e.g., "drop the old column"), warn them about the impact and suggest a standalone script rather than doing it inline.
- Destructive operations are irreversible. Confirm scope, ask for approval, and prefer running them manually rather than via an automated tool call.
- If a one-time destructive migration is truly needed, run it as a standalone script — not in a migration runner that fires at deploy time.

## 2. All Migration DDL Must Be Idempotent

Every DDL statement in a migration must be safe to run multiple times:

- `CREATE TABLE IF NOT EXISTS`
- `ADD COLUMN IF NOT EXISTS`
- `CREATE INDEX IF NOT EXISTS`
- `DROP INDEX IF EXISTS` (only when dropping is approved)

For conditional logic that PostgreSQL DDL alone cannot express, use a `DO $$ ... END $$` anonymous block:

```sql
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'foo' AND column_name = 'bar'
    ) THEN
        ALTER TABLE foo ADD COLUMN bar TEXT;
    END IF;
END $$;
```

Non-idempotent migrations break re-runs and make recovery from failed deployments painful.

## 3. Parameterized Queries Only

**NEVER** build SQL by concatenating user-controlled input into a string.

Bad:
```python
cur.execute(f"SELECT * FROM users WHERE email = '{email}'")
cur.execute("SELECT * FROM users WHERE id = " + user_id)
```

Good:
```python
cur.execute("SELECT * FROM users WHERE email = %s", (email,))  # psycopg2
cur.execute("SELECT * FROM users WHERE id = $1", [user_id])    # asyncpg
```

Use the driver's placeholder syntax (`%s` for psycopg2, `$1`/`$2` for asyncpg/libpq, `?` for sqlite3, `:name` for SQLAlchemy named params). The same rule applies to ORM `.raw()` calls.

## 4. Read-Only by Default

The default assumption for any database interaction is `SELECT`. Mutations (INSERT, UPDATE, DELETE) require explicit user approval unless:

- The user is actively running a script they wrote and asked you to execute.
- The operation is part of an approved, idempotent migration the user has reviewed.

When in doubt, show the SQL to the user and ask before running it.

## 5. Transaction Discipline

- Use explicit `BEGIN`/`COMMIT` where atomicity is required. Do not rely on auto-commit for multi-statement mutations.
- **Keep transactions short.** Do not wrap long-running compute, HTTP calls, or sleep inside a transaction — idle-in-transaction connections block vacuuming and hold locks.
- **Do not leave transactions open across async boundaries.** An `await` inside a transaction can leave a connection idle-in-transaction indefinitely.
- Use `SAVEPOINT` for partial rollback within a larger transaction when individual steps may fail.
- Use `autocommit=True` for DDL statements and for read-only connections that don't need transactional semantics.

## 6. Migrations Run at Deploy Time Only

**NEVER** call a migration runner from a scheduled job, scraper, or background task.

Running migrations concurrently with live queries can cause `AccessExclusiveLock` conflicts. If a migration holds a lock that a live query is waiting for, it can:
- Stall the running job mid-operation
- Drop or alter columns that the job is actively reading
- Cause cascading failures in dependent services

Migration runners belong in the deploy step only — invoked once, before traffic is restored.

## 7. Lock Timeout

Set a short `lock_timeout` before any DDL migration to prevent a migration from waiting indefinitely for a lock held by a long-running query:

```sql
SET lock_timeout = '5s';
ALTER TABLE foo ADD COLUMN IF NOT EXISTS bar TEXT;
```

If the lock cannot be acquired within the timeout, the migration fails fast with a clear error rather than silently blocking production traffic. Retry at a quieter time.
