---
name: handoff
description: "End-of-session tidy-up: close open loops, sync plan docs and memory, and leave the project in a state a fresh agent (or dev) can pick up without this conversation. Invoke via /handoff."
disable-model-invocation: true
---

# Session Handoff

Prepare the project for the next agent or developer. The bar for every step is
the **fresh-agent test**: could someone with access to the repo and persistent
memory — but *not* this conversation — pick up exactly where we left off?
Anything that lives only in chat history fails the test and must be written
down or surfaced.

## Step 1: Sweep in-flight work

Check for anything still moving or unsaved:

```bash
git status --short --branch
git log @{upstream}..HEAD --oneline 2>/dev/null
git branch --no-merged main 2>/dev/null
```

- **Background tasks/agents still running** — wait for them or report what was
  abandoned and why.
- **Uncommitted changes** — commit them (on the right branch), or if they are
  genuinely unfinished, say so explicitly in the summary; never leave silent
  dirty state.
- **Unpushed commits** — push, or if pushing needs the user (permissions,
  protected branch), list the exact command for them to run.
- **Stray local branches** — note any unmerged branches and what they contain.

## Step 2: Sync the plan documents

Locate the project's plan/progress docs — check `CLAUDE.md` for pointers
(e.g. `specs/PLAN.md`, feature-specific plan files, `TODO.md`). For each one
touched by this session's work:

- Mark completed items done **with the date and PR number**.
- Correct anything the session made stale (items marked "pending" that
  actually shipped, superseded decisions, changed scope).
- Make the **next step explicit and self-contained**: name the item, the
  concrete values it needs (IDs, URLs, paths, account refs discovered during
  the session), and the entry-point files. "Do X" is not enough if X requires
  knowledge that currently exists only in this chat.

## Step 3: Update the changelog

If the project keeps a changelog, confirm everything that shipped this
session has a terse entry (with PR/issue number) in the right section. One
line per change; trivial edits need no entry.

## Step 4: Update persistent memory

Update the auto-memory directory (topic files + the `MEMORY.md` index):

- Record **what was done** (with PR numbers), **decisions and their why**, and
  the **exact next step** with pointers.
- Convert relative dates ("today", "next week") to absolute dates.
- Prune: remove or mark-resolved any "next step" or "open issue" notes that
  this session completed — stale memory is worse than no memory.
- If review/audit agents maintain memory or baseline files
  (`.claude/agent-memory/*/`), mark items resolved by this session with a
  date.

## Step 5: Inventory open loops

List every loop the session opened that is not yet closed, and verify each
one is recorded in a durable place (plan doc, changelog, memory, issue —
not just chat):

- **Open PRs** awaiting review/merge, and any post-merge follow-up commands.
- **Manual steps only the user can do** (dashboard config, portal settings,
  deploys, secrets) — state them as a checklist with exact locations.
- **Time bombs**: expiring credentials/secrets/certs, scheduled rotations,
  ramp/cleanup dates. Include the actual expiry date, not "in 6 months".
- **Deferred items**: hardening tasks, known gaps, review findings
  intentionally postponed — each needs a home in a tracking doc with the
  reasoning for the deferral.

## Step 6: Produce the handoff summary

End with a compact summary in this format:

```
## Handoff Summary

Shipped this session: <one line per PR/change, with numbers>
Repo state: <branch, clean/dirty, anything unpushed + the command to push it>
Next step: <the single next task, with entry-point files/values>
Waiting on user: <manual steps, approvals — or "nothing">
Time-sensitive: <expiring secrets/dates — or "none">
Where it's written down: <plan doc(s), memory files updated>
```

Then apply the fresh-agent test one final time: re-read the "Next step" line
and ask whether a new agent could execute it from the named files alone. If
not, go back to Step 2.

Do **not** start new feature work from this skill — its job is to close the
session, not extend it.
