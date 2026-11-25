# Authoring rules

## What rules are

Rules are markdown files in `.claude/rules/` that Claude Code auto-loads as project instructions. A rule with no frontmatter loads at session start into **every** conversation. A rule with `paths:` frontmatter loads only once Claude reads, writes, or edits a file matching one of its globs (see [Path-scoped rules](#path-scoped-rules)).

Rules live in `base/rules/` and `addons/<lang>/rules/` in clank. After install they land in `<target>/.claude/rules/`.

---

## Why rules inject into every context

Because unscoped rules are always loaded, they apply universally. This makes them powerful for enforcing invariants — "always do X", "never do Y" — that should hold regardless of what the user is asking.

The cost is also universal: every unscoped rule adds tokens to every conversation. A 200-line rule costs the same whether the current task is relevant to it or not. This shapes what belongs in a rule versus a skill or agent.

---

## What makes a good rule

**One topic per file.** A rule about code review should not also cover testing conventions. Separate concerns into separate files so users can install exactly what they need.

**Under ~200 lines.** Claude Code may truncate very long rules. If your rule is approaching 200 lines, extract the reference material into a separate file (a skill's supporting file, or a plugin doc) and link to it.

**Stable.** Rules load in every conversation. A rule that changes frequently generates surprises. Lock rules down to the principles; put the evolving details in docs or skills.

**Actionable.** A rule should tell Claude what to do, not just describe what exists. "Use the `code-reviewer` agent after modifying code" is actionable. "The code-reviewer agent is available" is not.

**Useful everywhere — or scoped.** An unscoped rule must earn its place in every session. If a rule only applies to certain files (one language, one subsystem), give it `paths:` frontmatter so it loads only when those files are touched.

---

## Path-scoped rules

Add YAML frontmatter with a `paths` list of globs to load a rule only when it is relevant:

```markdown
---
paths:
  - "**/*.py"
---

# Python Coding Style
...
```

`paths` is the only frontmatter field Claude Code reads from a rule. The rule loads the first time Claude reads, writes, or edits a matching file in the session, and costs nothing before that.

**Every language rule in `addons/<lang>/rules/` must be path-scoped to that language's file extensions.** A multi-language preset otherwise loads every language's style, testing, security, and patterns rules into every session.

Leave a rule unscoped only when it governs behavior that isn't tied to opening a particular file — process and safety rules such as `code-review`, `branch-per-feature`, `sql-safety` (SQL shows up inside any language's source and in MCP queries), or `release-discipline`.

---

## When NOT to use a rule

**Large reference material** (schemas, API docs, data dictionaries): put this in a skill with a supporting file, or in `plugins/`. Users browse it on demand; the model does not need it in every context.

**Single-task workflows** (deploy, migrate, query-db): use a user-invokable skill with `disable-model-invocation: true`. It stays out of the context until the user asks for it.

**Per-directory context** (a README that explains how a specific module works): use a `CLAUDE.md` at that directory level. Claude Code loads it only when working in that directory.

---

## Rule vs. agent vs. skill decision tree

```
"Always remember this when doing anything"
    → rule

"Delegate this type of work to a specialist"
    → agent

"Run this procedure when asked"
    → skill (with disable-model-invocation: true for user-invokable)

"This only matters for certain files"
    → rule with `paths:` frontmatter

"This only matters in one directory/module"
    → CLAUDE.md at that directory
```

---

## Adding a rule

1. Write the rule as a markdown file in `base/rules/<topic>.md` or `addons/<lang>/rules/<lang>-<topic>.md`. Language rules start with `paths:` frontmatter for that language's extensions.

2. Add an `[[artifacts]]` entry to `manifest.toml`:

```toml
[[artifacts]]
id = "code-review"
type = "rule"
path = "base/rules/code-review.md"
description = "When and how to conduct code review"
tags = ["base", "review", "process"]
```

3. Choose tags that map to the presets that need this rule. Base rules use the `"base"` tag (picked up by `@tag:base` and therefore by `base-only` and every preset that extends it). Language rules use the language tag (e.g. `"python"`) so they land in the `python` preset but not `base-only`.

---

## Generalizing rules from other projects

When lifting a rule from a production project:

- Strip all project-specific mentions: file paths, tool versions, table names, service names.
- Replace specific references with generic patterns. "The `players` table" → "your primary entities table". `"api-web.nhle.com/v1"` → not in a rule at all.
- Test that the rule still makes sense with no prior context about the project.
- If after stripping it says nothing useful, it was not a rule — it was project-specific context that belongs in `CLAUDE.md`.

---

## Examples

**`base/rules/code-review.md`** — when and how to run code review. Mandatory review triggers, agent to use, checklist, severity levels, workflow steps. Applies universally: every project benefits from knowing when to review.

**`base/rules/testing.md`** — TDD workflow (RED/GREEN/REFACTOR), AAA test structure, descriptive test names. Language-agnostic; examples use TypeScript but the pattern applies everywhere.

**`addons/python/rules/python-coding-style.md`** — a path-scoped language rule. `paths: ["**/*.py"]` keeps it out of context until Claude touches a Python file.
