# Branch Per Feature

## Rule

Every new feature, bugfix, or non-trivial change must be developed on a dedicated branch — never directly on `main` (or `master`/`develop`/any shared integration branch).

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

When in doubt, ask before committing to a shared branch.

## Remind, don't auto-switch silently

If the user asks for changes while on a shared branch, surface the branch situation in one short sentence and propose a branch name before starting the work. Do not create the branch silently — the user may have a reason to be on `main`.
