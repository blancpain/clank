# Authoring skills

## What a skill is

A skill is a markdown file that describes a procedure Claude should follow. Skills are activated either automatically (when Claude's routing matches the skill's description) or via an explicit `/<name>` user invocation.

Skills differ from agents: an agent is a subagent with its own context, tools, and memory. A skill is a procedure that runs in the main conversation — a set of steps Claude follows inline.

Skills live in `.claude/skills/<name>/` in the target project. The installer copies the entire directory recursively, so a skill can include supporting files alongside `SKILL.md`.

---

## Skill frontmatter

```yaml
---
name: review
description: "Run code review on recently modified code. Invoke via /review."
disable-model-invocation: true
---
```

### `name`

Unique identifier. For user-invokable skills, this becomes the `/command` name (e.g. `name: review` → `/review`).

### `description`

Shown in `/help` listings and used for auto-activation routing (if `disable-model-invocation` is not set). Write it to describe when the skill should be used.

### `disable-model-invocation: true`

When present, the skill activates **only** when the user types `/<name>` explicitly — never via description-match routing. Use this for:

- User-invokable workflows that should not fire automatically (deploy, migration, review)
- Procedures where you want the user to be deliberately in control

All clank user-facing skills (`review`, `deploy`, `smoke-test`, `querying-db`, `migration`) use `disable-model-invocation: true`.

---

## Skill directory structure

```
base/skills/review/
    SKILL.md          — the skill procedure (required)

addons/sql/skills/querying-db/
    SKILL.md          — the skill procedure (required)
    schema.txt.template  — supporting file shipped alongside the skill
```

The manifest `path` field points to the **directory**, not `SKILL.md`:

```toml
[[artifacts]]
id = "querying-db"
type = "skill"
path = "addons/sql/skills/querying-db"
description = "Read schema.txt then query via postgres MCP."
tags = ["sql", "postgres"]
```

The installer copies every file in the directory recursively into `<target>/.claude/skills/<name>/`. For single-file skills with no supporting files, this is equivalent to copying `SKILL.md` alone.

---

## When to use a skill vs. a rule

**Use a rule** when you want Claude to remember something in every conversation — a constraint, a discipline, a coding standard. Rules auto-load into every context.

**Use a skill** when you want Claude to follow a procedure on demand — a multi-step workflow that is only needed in specific situations. Skills are invoked explicitly (via `/name`) or when the user asks for something that matches the skill's description.

**Use an agent** when the work should be isolated in a separate context with its own tools — a long-running review, a research task, a read-only audit.

Quick decision:
- "Always remember this" → rule
- "Run this procedure when asked" → skill
- "Delegate this to a specialist with its own context" → agent

---

## Writing the skill body

A skill body is a numbered procedure. Be concrete: include shell commands, decision points, and exact output formats. Do not just describe what to do — show how.

Good skill body (from `base/skills/review/SKILL.md`):

```markdown
## Step 1: Identify Changes

Run `git diff HEAD` to capture staged and unstaged changes:

```bash
git diff HEAD
```

If there are no changes (empty output), report "No changes to review" and stop.

## Step 2: Dispatch code-reviewer

Using the Task tool, dispatch the `code-reviewer` agent **in the background** with
the list of changed files as context. Do NOT wait for it before proceeding to Step 3.
```

The key qualities:
- Numbered steps with clear exit conditions ("if empty, stop")
- Concrete commands, not vague instructions
- Decision branches that tell Claude exactly what to do in each case

---

## User-invokable skill pattern

User-invokable skills follow a consistent pattern:

1. `name` matches the `/command` the user types
2. `disable-model-invocation: true` in frontmatter
3. Body is a step-by-step procedure, not a description

Example: `/review` invokes `base/skills/review/SKILL.md`. `/deploy` invokes `base/skills/deploy/SKILL.md`. `/querying-db` invokes `addons/sql/skills/querying-db/SKILL.md`.

This pattern comes from ice-scraper, where `/migration` and `/deploy` are user-invokable entry points for project-specific workflows.

---

## Scaffold skills

Some skills ship as placeholders that the user fills in after install. The `deploy` skill is the canonical example:

```markdown
## Deploy Command

```
# TODO: Fill in your project's deploy command here.
# Examples:
#   ssh user@host "cd /app && git pull && systemctl restart svc"
#   kubectl rollout restart deployment/foo
#   vercel --prod
```
```

Use `# TODO: fill in ...` comments to mark every section the user must customize. The pre-flight and post-deploy verification sections can be fully written; only the project-specific commands need placeholders.

---

## Examples

**`base/skills/review/SKILL.md`** — auto-structured workflow with `disable-model-invocation: true`. Dispatches `code-reviewer` and optionally `security-reviewer` in parallel, then consolidates findings into a single report. No supporting files.

**`base/skills/deploy/SKILL.md`** — scaffold skill with `disable-model-invocation: true`. Ships a complete workflow (pre-flight → deploy → verify → rollback) with `# TODO` placeholders for the deploy command and health check. The user edits this once after install.

---

## External skills (fetched via `npx skills`)

For skills published to [skills.sh](https://skills.sh) that you'd rather pull fresh at install time than vendor into clank, use the `external-skill` artifact type. The installer shells out to `npx skills add <source> --skill <skill_name> --copy` inside the target directory, which lands the skill at `<target>/.claude/skills/<skill_name>/`.

```toml
[[artifacts]]
id = "find-skills"
type = "external-skill"
source = "vercel-labs/skills"
skill_name = "find-skills"
description = "Discover skills from skills.sh at runtime. Fetched via `npx skills add`; requires Node."
tags = ["base", "meta"]
default = false
```

- `source` is the repo reference passed to `npx skills add` (e.g. `vercel-labs/skills`, or a full URL).
- `skill_name` is both the `--skill` argument and the directory name the skill gets installed into. Use it for `--uninstall` symmetry.
- Do **not** set `path` — external skills have no source inside clank.
- Keep `default = false`. External skills require Node at install time; users opt in via `--include`.
- Uninstall is supported: clank removes `<target>/.claude/skills/<skill_name>/` and updates the receipt.
- If `npx` is missing, the installer warns and skips the artifact rather than failing the whole run — same pattern as lint hooks.

**`addons/sql/skills/querying-db/SKILL.md`** — skill with a supporting file. `SKILL.md` describes the query procedure; `schema.txt.template` is a scaffold the user fills in with their actual schema. The installer copies both files into `.claude/skills/querying-db/`.
