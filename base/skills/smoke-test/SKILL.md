---
name: smoke-test
description: "Pre-flight checklist for long-running scripts. Invoke via /smoke-test."
disable-model-invocation: true
---

# Smoke Test — Pre-Flight Checklist

Run this checklist before any script that will take more than 1 minute. A 30-second dry run prevents losing hours to a late crash.

## Check 1: Imports Resolve

Verify the script's top-level imports work without errors:

```bash
python -c 'import <module_name>'
```

For TypeScript/Node:
```bash
node -e 'require("./<entry>")'
```

If this fails, fix the import error before proceeding.

## Check 2: Dependencies Installed

Confirm required packages are present:

```bash
pip list | grep <package>
npm ls <package>
cargo check
go build -o /dev/null ./...
```

If any dependency is missing, install it and re-run the check.

## Check 3: DB / Service Connection

If the script connects to a database or external service, verify the connection:

**PostgreSQL:**
```bash
psql $DATABASE_URL -c "SELECT 1"
```

**HTTP API:**
```bash
curl -sSf -o /dev/null -w "%{http_code}" https://your-api/health
```

If the connection fails, resolve it before running the full script.

## Check 4: Available Memory

Check available memory and compare against the script's estimated peak usage:

**Linux:**
```bash
free -m
```

**macOS:**
```bash
vm_stat | grep "Pages free"
```

If available memory is less than 2x the script's estimated peak usage, warn the user. Large datasets, full-table scans, and unvectorized pandas loops are common culprits.

## Check 5: Tiny-Subset Dry Run

Run the script on a minimal fraction of the input — one date, one record, or a `--limit 1` flag:

```bash
python script.py --date 2024-01-01
python script.py --limit 1 --dry-run
```

Verify:
- No immediate crashes or unhandled exceptions
- Output format is correct (spot-check the first record)
- Log level is appropriate — not DEBUG spamming stdout

## Approval Gate

After all 5 checks pass, present a summary:

```
Smoke test results:
  Imports:      OK
  Dependencies: OK
  Connection:   OK
  Memory:       <available>MB available / ~<estimated>MB estimated peak
  Dry run:      OK — <sample output>

Ready to run full script?
```

**Do NOT auto-proceed.** Ask the user to confirm before launching the full run.
