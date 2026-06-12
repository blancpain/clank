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
git branch --no-merged "$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null || echo main)" 2>/dev/null
```

(Use the repo's actual default/integration branch — don't assume `main`.)

- **Background tasks/agents still running** — wait for them or report what was
  abandoned and why.
- **Uncommitted changes** — commit them (on the right branch), or if they are
  genuinely unfinished, say so explicitly in the summary; never leave silent
  dirty state.
- **Unpushed commits** — push, or if pushing needs the user (permissions,
  protected branch), list the exact command for them to run.
- **Stray local branches** — note any unmerged branches and what they contain.

## Step 2: Sync the plan documents

The canonical plan doc is `docs/plan.md` (see `rules/project-docs.md`); in a
project that predates the convention, follow the `CLAUDE.md` `## Status`
pointer to wherever its plan docs live (e.g. `specs/PLAN.md`, `TODO.md`). If
the canonical docs are missing entirely, create them per the convention as
part of this handoff — never overwrite existing content. For each plan doc
touched by this session's work:

- Mark completed items done **with the date and PR number**.
- Correct anything the session made stale (items marked "pending" that
  actually shipped, superseded decisions, changed scope).
- Make the **next step explicit and self-contained**: name the item, the
  concrete values it needs (IDs, URLs, paths, account refs discovered during
  the session), and the entry-point files. "Do X" is not enough if X requires
  knowledge that currently exists only in this chat.

## Step 3: Update the changelog

Confirm everything that shipped this session has a terse, dated entry (with
PR/issue number) at the top of `CHANGELOG.md` — shipped items move OUT of
the plan and INTO the changelog, in the same handoff. One line per change;
trivial edits need no entry. Refresh the `## Status` section in `CLAUDE.md`
if the current focus changed.

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
