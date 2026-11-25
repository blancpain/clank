---
name: agent-review
description: "Run the project's reviewer agents (code-reviewer, plus security-reviewer when relevant) on recently modified code. Invoke via /agent-review."
disable-model-invocation: true
---

# Agent Review

Run `code-reviewer` (and optionally `security-reviewer`) on recent changes.

This is the project's own review, driven by its reviewer agents and their
memory. It is separate from Claude Code's bundled `/code-review` (and its
`/review` alias), which is why it has a different name.

## Step 1: Identify Changes

Run `git diff HEAD` to capture staged and unstaged changes:

```bash
git diff HEAD
```

If reviewing a branch against a base (e.g. `main`), also run:

```bash
git diff main..HEAD
```

Extract the list of changed file paths:

```bash
git diff HEAD --name-only
```

If there are no changes (empty output), report "No changes to review" and stop.

## Step 2: Dispatch code-reviewer

Using the Agent tool, dispatch the `code-reviewer` agent **in the background** with the list of changed files as context. Do NOT wait for it before proceeding to Step 3.

Pass the diff output and file list so the agent has full context.

## Step 3: Check for Security-Sensitive Changes

Scan the diff for security-relevant keywords:

```bash
git diff HEAD | grep -iE 'auth|login|session|token|password|secret|api[_-]?key|crypto|hash|hmac|cipher|encrypt|decrypt|sql|query|execute|subprocess|shell|eval|exec|pickle|yaml\.load|deserializ|xml|xxe|url|request|fetch|cookie|csrf|xss|sanitiz|escape|input|upload'
```

If this grep returns any matches, the changes touch security-sensitive areas.

## Step 4: Conditionally Dispatch security-reviewer

If Step 3 found security-relevant keywords, dispatch the `security-reviewer` agent **in the background** (in parallel with `code-reviewer`). Pass the same diff and file list.

If Step 3 found nothing, skip this step — `code-reviewer` alone is sufficient.

## Step 5: Wait for Agent Results

Wait for both agents (or just `code-reviewer` if security-reviewer was skipped) to complete. Their findings arrive as tool results.

## Step 6: Consolidate Findings

Merge the findings into a single report:

- Collect all **Critical** issues from both agents. If the same issue was flagged by both, mention it once and note "flagged by both reviewers".
- Collect all **High**, **Medium**, and **Low** issues similarly — deduplicate overlapping findings.
- Determine the overall **Verdict**:
  - `BLOCK` if any Critical issues exist
  - `WARNING` if only High issues exist (no Critical)
  - `APPROVE` if only Medium/Low (or no issues)

## Step 7: Present Consolidated Report

Output the report in this format:

```
## Review Summary

Files reviewed: <N> (<list file names>)
Agents: code-reviewer[, security-reviewer]

Critical (N): ...
High (N):     ...
Medium (N):   ...
Low (N):      ...

Verdict: APPROVE | WARNING | BLOCK
```

Do **NOT** auto-fix any issues. Present the findings and let the user decide which to address.
