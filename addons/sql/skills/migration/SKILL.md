---
name: migration
description: Create a new database migration. Scaffold — edit the 'Your migration system' section after install to describe your project's specific workflow. Invoke via /migration.
disable-model-invocation: true
---

# Create a Database Migration

Generate a safe, idempotent migration for the schema change the user describes.

## Arguments

The user should describe the schema change they want (e.g., "add column `foo` to `bar`", "create table `baz`", "add index on `created_at`").

## Safety Rules (mandatory)

1. **NEVER** use `DROP TABLE`, `DROP COLUMN`, `TRUNCATE`, or `DELETE` without `WHERE` in a migration. If the user asks for a destructive change, warn them and suggest a standalone script instead.
2. **All DDL must be idempotent**: use `IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`, etc.
3. **Migrations run at deploy time only** — NEVER call the migration runner from a scheduled job, scraper, or background task. Concurrent migration + live query can cause lock contention and dropped columns mid-operation.
4. **Lock timeout**: set `SET lock_timeout = '5s'` before DDL to fail fast rather than blocking production indefinitely.

## SQL Patterns

**Add column:**
```sql
ALTER TABLE table_name ADD COLUMN IF NOT EXISTS column_name TYPE DEFAULT value;
```

**Create table:**
```sql
CREATE TABLE IF NOT EXISTS table_name (
    id BIGINT PRIMARY KEY,
    ...
);
```

**Create index:**
```sql
CREATE INDEX IF NOT EXISTS idx_name ON table_name(column1, column2);
```

**Complex / multi-statement** — wrap in a `DO $$ ... END $$` block:
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

**With lock timeout:**
```sql
SET lock_timeout = '5s';
ALTER TABLE foo ADD COLUMN IF NOT EXISTS bar TEXT;
```

## Your Migration System — edit this

```
# TODO: Fill in your project's migration workflow.
#
# Examples:
# - Alembic: `alembic revision -m "<description>" --autogenerate`
# - Django migrations: `python manage.py makemigrations && python manage.py migrate`
# - Raw SQL files: put the SQL in migrations/<timestamp>-<description>.sql
# - golang-migrate: `migrate create -ext sql -dir db/migrations <name>`
# - Python MIGRATIONS list: append the SQL to MIGRATIONS in your schema module
```

## Verify

After generating the migration, show the user:

- The exact SQL that will run
- Where it was added (file path and location within the file)
- Any DDL or schema reference files that also need updating
