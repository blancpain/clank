# Branch Per Feature

## Rule

Every new feature, bugfix, or non-trivial change must be developed on a dedicated branch and land in `main` (or the project's integration branch) via a pull request — never by direct commit or push to the shared branch.

**Exception — standalone prose docs.** Edits that touch *only* prose documentation (`README`, `CHANGELOG.md`, `docs/`, `docs/plan.md`, `CLAUDE.md`) may be committed straight to `main` — no branch, no PR. This is the common case for plan/changelog/status upkeep, and the PR ceremony adds nothing. It applies **only** when the change is documentation-and-nothing-else: docs that accompany a code change ride in that change's branch/PR, and behavioral config (`.claude/rules/*`, skills, hooks, agents) and code are **not** prose docs — they keep the branch/PR flow.

## When to create a branch

**Before making any code changes**, check the current branch:

```bash
git branch --show-current
```

If the current branch is `main`, `master`, `develop`, or another shared/protected branch, create and switch to a new branch **before** editing files:

```bash
git checkout -b <type>/<short-description>
```

Conventional prefixes:

- `feat/` — new feature
- `fix/` — bug fix
- `refactor/` — internal restructuring, no behavior change
- `docs/` — documentation only
- `chore/` — tooling, config, deps

Examples: `feat/user-login`, `fix/null-ref-in-parser`, `refactor/extract-auth-service`.

## Exceptions

Direct commits to the current branch are acceptable only when:

- The user has explicitly said "commit to this branch" or "stay on main"
- The current branch is already a feature branch (not a shared branch)
- The change is a trivial one-line fix the user has explicitly asked to land on `main`
- The change is **standalone prose documentation** (README, CHANGELOG, `docs/`, `plan.md`, `CLAUDE.md` — see the exception under "## Rule") — commit straight to `main`, no branch needed

When in doubt, ask before committing to a shared branch.

## Remind, don't auto-switch silently

If the user asks for changes while on a shared branch, surface the branch situation in one short sentence and propose a branch name before starting the work. Do not create the branch silently — the user may have a reason to be on `main`.

## Land changes via a pull request

Once the work on the feature branch is ready, the change ships by opening a pull request against the integration branch — not by pushing commits directly to `main`.

- **Push the branch first**, then open the PR. Use `gh pr create` (or the project's equivalent) with a title and description that explain the *why*, not just the *what*.
- **One logical change per PR.** If the branch has grown to cover multiple unrelated concerns, split it before requesting review — reviewers should not have to untangle intent.
- **Never force-push to `main`** and never merge your own PR without the review/CI gates the project requires. If the project has no gates configured, still prefer opening a PR so the diff is reviewable, even if you end up merging it yourself.
- **Do not open the PR silently.** Confirm with the user before pushing the branch or creating the PR unless they have already authorized it for this task — pushing and PR creation are visible to others and hard to quietly undo.
- **The PR is the default you're confirming, not one option in a menu.** When you check in about landing, lead with the PR; do not present direct-merge-to-`main` as a co-equal choice. The user reaches direct-merge only on their own initiative (see Exceptions).

### Exceptions to the PR requirement

Skip the PR when the change is **standalone prose documentation** (README, CHANGELOG, `docs/`, `plan.md`, `CLAUDE.md` — see the exception under "## Rule"); it needs neither a branch nor a PR. Otherwise skip the PR only when the user **proactively, unprompted** says so ("just commit and push", "no PR needed", "land it directly") — a choice the user makes from options *you* put in front of them does **not** count — or when the project's documented workflow genuinely doesn't use PRs (e.g. a solo scratch repo). When in doubt, ask.
