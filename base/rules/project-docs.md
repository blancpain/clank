# Project Docs Convention

Every project keeps the same three living documents, so session tooling
(`/pickup`, `/handoff`, doc audits) and humans always know where state lives.

## The canonical set

| File | Role | Maintained when |
|------|------|-----------------|
| `docs/plan.md` | What's in flight (`## Now`), what's queued (`## Queued`), what's parked (`## Later / external`) | Priorities shift, work starts, scope changes |
| `CHANGELOG.md` | Dated log of what shipped, newest first, terse | Something merges/ships |
| `CLAUDE.md` `## Status` | Two/three-line pointer: current focus + "read `docs/plan.md` before starting work" | A thread starts or ends |

The shipping ritual: when something lands, **move** it — delete the plan
entry, write the changelog entry (with PR number and date), refresh the
Status line. The plan holds only the future; the changelog holds only the
past; CLAUDE.md holds only durable facts plus the pointer.

## Rules

- **CLAUDE.md stays thin.** Status is a pointer, not a narrative. Durable
  facts (architecture, invariants, hard-won gotchas) belong in CLAUDE.md's
  body; everything time-bound goes in the plan or changelog.
- **Plan entries must pass the fresh-agent test**: a new session should be
  able to start any queued item from its bullet alone — name the entry-point
  files, IDs, URLs, and constraints discovered so far.
- **Changelog entries record the why**, not the diff: the key decision, the
  verification status, anything a future reader can't reconstruct from code.
- **Don't fork the convention.** No parallel TODO.md / NOTES.md / plan-v2;
  if a project genuinely needs more structure (per-feature spec files),
  link them from `docs/plan.md` so it stays the single index.
- If the project predates this convention and uses different paths, either
  migrate or add a `## Status` section to CLAUDE.md pointing at the actual
  locations — tooling follows the pointer.

## First-time setup

If any piece of the canonical set is missing, complete it during the first
`/handoff` (or `/pickup`) that touches the project: create `docs/plan.md` /
`CHANGELOG.md` from the skeletons if absent (the clank installer scaffolds
them only for projects that lack them), and **add the `## Status` section to
CLAUDE.md if it doesn't exist yet** — the installer never writes it. Never
overwrite existing content.
