---
name: pickup
description: "Start-of-session orientation: read memory and plan docs, verify them against repo/PR/prod reality, and produce a trustworthy picture of where work stands and what's next. The mirror of /handoff. Invoke via /pickup [optional topic]."
disable-model-invocation: true
---

# Session Pickup

Orient a fresh session before any work starts. The bar for every step is the
**stale-memory test**: written state (memory, plan docs) reflects the moment it
was written — the repo, PRs, and production may have moved since. Never act on
a recorded "next step" until you have confirmed it is still the next step.

If the user passed a topic argument, scope the pickup to it; otherwise pick up
whatever the memory/plan docs mark as the active thread.

## Step 1: Gather the written state

- Read the auto-memory index (`MEMORY.md`) and **open the topic files** behind
  every entry relevant to the task — the index lines are hooks, not content.
- Follow `CLAUDE.md` pointers to plan/progress docs (e.g. `specs/PLAN.md`,
  feature plan files, `TODO.md`) and read the sections marked in-progress or
  "next".
- Note the changelog's `[Unreleased]` section — it lists what recently shipped.
- Collect every concrete claim worth verifying: "PR #N merged", "deployed",
  "verified on prod", "expires on \<date\>", "branch X awaiting review".

## Step 2: Verify against reality

```bash
git fetch --quiet
git status --short --branch
git log origin/main --oneline -10
gh pr list --state open 2>/dev/null
gh pr list --state merged --limit 5 2>/dev/null
```

- **PRs**: did anything merge (or get closed) since the written state? Did a
  stacked/dependent PR land in the right base? Don't trust a MERGED state
  alone — confirm the content actually reached main (grep for a marker the
  change introduced).
- **Working tree**: uncommitted changes or unpushed commits left behind?
  Unmerged local branches? Understand them before touching anything.
- **Prod/external claims**: if a claim is cheap to check (a `curl` to an
  endpoint, a CLI status call), check it rather than trusting it.
- **Time bombs**: compare every recorded expiry/rotation/ramp date against
  today's date; surface anything past due or due within ~2 weeks.

## Step 3: Reconcile

- **Reality ahead of the docs** (PR merged, deploy done, manual step
  completed): update the plan doc / memory marks now, so the drift dies here.
- **Docs ahead of reality** (claims "done" but the change isn't on main /
  prod): flag this loudly — fixing the discrepancy probably *is* the next
  step. Do not build on top of it.
- Prune or correct memory entries this verification proved stale.

## Step 4: Produce the pickup brief

End with a compact brief in this format:

```
## Pickup Brief

Where we left off: <one-line thread summary, with PR numbers>
Changed since handoff: <merges, deploys, drift found — or "nothing">
Verified next step: <the single next task, entry-point files/values, confirmed still valid>
Blockers / waiting on user: <manual steps, approvals — or "nothing">
Time-sensitive: <past-due or upcoming dates — or "none">
```

Then state the first concrete action you propose to take. If the session has
an explicit task from the user, proceed into it; if the next step was inferred
from memory/plans alone, confirm scope with the user before starting.

Do **not** begin feature work inside this skill — its job is to orient and
verify, not to extend. (Closing the drift found in Step 3 is in scope.)
