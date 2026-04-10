# Update Agent Memory After Resolving Issues

After fixing issues surfaced by an agent audit (e.g., after fixing issues surfaced by any agent that maintains an audit baseline or memory state), update that agent's memory/baseline files to reflect the resolved state before ending the session.

Files to check: `.claude/agent-memory/*/` — especially `audit_baseline.md`.

Mark resolved items as done with a date, remove stale entries, and record what was changed.
