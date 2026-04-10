# Long-Running Scripts

## Smoke-test first

Before running any script that takes >1 minute (backtests, seed scripts, signal generation), do a quick dry run on a single date or small subset to verify:

- Imports resolve
- DB connection works
- Dependencies are installed
- Output format is correct
- Available memory (not just free) against expected usage

A 30-second dry run prevents losing hours to a late crash.

## Optimize before running

Before executing any computationally expensive script (backtests, bulk inserts, full-season processing), review the code for optimization opportunities:

- Batch DB operations instead of row-by-row inserts
- Vectorize pandas loops
- Avoid redundant queries
- Use appropriate indexing
- Eliminate unnecessary data loading

A few minutes spent optimizing can turn a 2-hour run into a 10-minute one without sacrificing correctness.
