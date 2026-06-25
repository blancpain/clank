---
name: merge
description: "Merge the current branch's pull request with a rebase merge via gh. Invoke via /merge."
disable-model-invocation: true
---

# Merge PR (rebase)

Merge a pull request using GitHub's **rebase** strategy via the `gh` CLI. By
default this targets the PR for the current branch; an argument can name a
specific PR (number, URL, or branch).

## Step 1: Identify the PR

If the invocation included an argument (PR number, URL, or branch), use it as
`<pr>` in the commands below. Otherwise omit it and `gh` resolves the PR from
the current branch.

Confirm a PR exists and inspect its state before merging:

```bash
gh pr view <pr> --json number,title,state,mergeable,reviewDecision,statusCheckRollup,headRefName,baseRefName
```

If no PR is found (or `state` is not `OPEN`), report that and stop — there is
nothing to merge.

## Step 2: Report status and confirm

Summarize for the user before doing anything irreversible:

- PR number + title, `headRefName` → `baseRefName`
- `mergeable` (e.g. `MERGEABLE`, `CONFLICTING`)
- `reviewDecision` (e.g. `APPROVED`, `REVIEW_REQUIRED`)
- CI status from `statusCheckRollup` — note any failing or pending checks

Merging is outward-facing and hard to reverse. **Always show the exact command
and ask the user to confirm** before running it — unless they already said to
merge without asking in this turn.

```bash
gh pr merge <pr> --rebase --delete-branch
```

Do not merge when `mergeable` is `CONFLICTING`, or when required checks are
failing/pending, unless the user explicitly tells you to override. If they want
to wait for checks, prefer auto-merge (Step 4).

## Step 3: Merge

Once confirmed, run the rebase merge and delete the source branch:

```bash
gh pr merge <pr> --rebase --delete-branch
```

Drop `--delete-branch` if the user wants to keep the branch. If the merge is
blocked by branch protection and the user has rights and explicitly asks to
force it, `--admin` bypasses required checks — only with clear instruction.

## Step 4: Auto-merge (optional)

When checks are still running and the user wants it to land once they pass:

```bash
gh pr merge <pr> --rebase --delete-branch --auto
```

This queues the merge; GitHub completes it when all required checks succeed.

## Step 5: Report the outcome

Report what happened: merged now, queued for auto-merge, or blocked (and why).
On a successful immediate merge, confirm the branch was deleted. Quote any error
`gh` returned verbatim rather than paraphrasing it.
