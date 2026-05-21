# No Redundant Code Review

Do not re-run a code-review subagent on a diff that has already been reviewed in this conversation. This applies to any agent whose job is to review a diff — typically named `*-reviewer`, plus close cousins like `database-reviewer` or `pipeline-validator`. Once a reviewer returns a verdict, the next step is to act on its findings — not to dispatch another review of the same code.

## Re-review only if

- New code has been written or the diff has materially changed since the last review.
- The user explicitly asks for another pass.
- A different reviewer is warranted (e.g., `code-reviewer` ran but the diff touches auth/crypto/SQL and `security-reviewer` has not yet run).

In the third case, only dispatch the reviewer that has not run — do not re-dispatch one that already finished.

## Why

Stop hooks, `/review` skills, and proactive reminders can keep prompting Claude to run code review. Without a stop condition, this produces back-and-forth loops where the same diff is reviewed repeatedly, burning tokens and rarely surfacing new findings.

## How to apply

When something (a reminder, a hook, a skill, your own instinct) prompts a code review:

1. Scan the conversation history. Did a review subagent already run, and is the current diff the same as what it saw?
2. If yes and the diff is unchanged: skip the dispatch. Acknowledge the prompt by restating the prior verdict, then move on (fix findings, or proceed if approved).
3. If the diff has grown: review only the new portion, not the full diff.
4. If no prior review exists: proceed as normal.

The `review-before-commit` hook in particular fires at `git commit` time. If the reviewer just ran on the current diff, treat the block as satisfied — re-run `git commit` (which the hook will pass through within its window) instead of dispatching another review.
