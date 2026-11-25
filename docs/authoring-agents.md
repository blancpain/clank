# Authoring agents

## What an agent is

An agent is a markdown file with YAML frontmatter that defines a specialist subagent Claude can delegate to. When Claude Code encounters a task that matches the agent's description, it can spin up the agent in a separate context with its own tool set and instructions.

Agents live in `.claude/agents/` in the target project. clank sources them from `base/agents/` and `addons/<lang>/agents/`.

---

## Frontmatter fields

```yaml
---
name: my-agent
description: "Use this agent when ... (router signal)"
model: sonnet
color: cyan
tools: Read, Grep, Glob, Bash
memory: project
---
```

### `name`

Unique identifier for the agent. Must be unique across all agents installed in a project. Used as the agent's label in the UI and as the directory name for its memory (`.claude/agent-memory/<name>/`).

### `description`

The **router signal** — the text Claude matches against user intent to decide whether to delegate to this agent. Write it as "use when..." not as human documentation. It is not shown to the agent itself; it is only used for routing.

Good description (router signal):
```
"Expert Python code reviewer. Use PROACTIVELY when reviewing Python code — FastAPI endpoints, async code, DataFrame pipelines, or any Python file."
```

Bad description (human documentation, not a router signal):
```
"This agent knows about Python best practices and can help with code quality."
```

The difference: the good version tells Claude *when* to invoke the agent. The bad version describes the agent's knowledge but gives Claude no guidance on when to use it.

### `model`

Which Claude model the agent runs on. Options: an alias (`sonnet`, `opus`, `haiku`, `fable`), a full model ID, or `inherit` to use the main conversation's model. When omitted, the agent also inherits the main conversation's model. Match model to task:

- `sonnet` — default for most reviewers and researchers (good balance of quality and speed)
- `opus` — complex reasoning tasks, architecture-level decisions
- `haiku` — lightweight tasks where speed matters more than depth

### `color`

Optional. Sets the agent's label color in the Claude Code UI. Useful for visual distinction when multiple agents are active in parallel. Common values: `cyan`, `yellow`, `green`, `red`, `purple`.

### `tools`

Comma-separated list of Claude Code tools the agent is allowed to use. Always be explicit — do not omit this field.

Common combinations:
- Read-only auditor: `Read, Grep, Glob, Bash` (Bash for `git diff`, `python -c` checks only). Never list `Edit` or `Write` on an agent whose prompt says read-only.
- Researcher: `Read, Grep, Glob, Bash, WebFetch`
- Writer: `Read, Grep, Glob, Bash, Edit, Write`
- Database auditor: `Read, Grep, Glob, Bash, mcp__postgres__*, mcp__supabase__execute_sql`

**MCP tools must be named here.** Once an agent has a `tools` list, it gets no MCP tool the list
doesn't name. Name one tool (`mcp__<server>__<tool>`) or a whole server (`mcp__<server>__*`).
A name that matches nothing in the project is ignored, so one agent can list the tools of
several alternative servers. Project hooks still run on MCP calls an agent makes.

### `memory`

Set to `project` if the agent should maintain memory files under `.claude/agent-memory/<name>/`. When set, the agent persists findings, patterns, and institutional knowledge across conversations.

Claude Code does the plumbing: it adds memory instructions and the start of the agent's `MEMORY.md` to the agent's system prompt, and it **automatically enables `Read`, `Write`, and `Edit`** so the agent can manage its memory files — whatever the `tools` list says. So a `memory: project` agent can always write files; the `tools` list alone cannot make it read-only (see [Read-only agent convention](#read-only-agent-convention)).

Omit this field for agents that don't need cross-conversation memory (e.g., one-shot researchers).

### `mcpServers`

Leave it out. Listing a server by name (`mcpServers: [postgres]`) does **not** give the agent that
server's tools when the agent also has a `tools` list — checked on Claude Code 2.1.332, where such
an agent could not call the server at all. Grant MCP tools through `tools` instead (see above).

The field's real use is an inline server definition that should exist only while the agent runs,
which no clank agent needs.

---

## Writing the description for routing

The description is the single most important field. Claude uses it to decide whether to invoke the agent. Write it to match the natural language a developer would use when asking for that kind of help.

**Pattern:** "Expert [domain] [role]. Use [when/trigger condition] — [specific examples of tasks]."

Examples from clank:

```
"Expert code review specialist. Use this agent PROACTIVELY to review code for quality,
security, and maintainability. Use immediately after writing or modifying code."
```

```
"Expert Python code reviewer. Use PROACTIVELY when reviewing Python code — FastAPI
endpoints, async code, DataFrame pipelines, or any Python file. Use alongside the
base code-reviewer for language-specific depth."
```

The word `PROACTIVELY` signals that Claude should invoke without waiting for an explicit user request. Use it for reviewers and auditors.

---

## Read-only agent convention

Most clank reviewer agents are read-only auditors — they report findings but do not modify files. Enforce this explicitly in the agent prompt, immediately after the frontmatter:

```markdown
**You are a strictly read-only auditor. You MUST NOT modify any files, run chmod,
create files, or make any changes whatsoever — not even to /tmp. Your only job is to
READ code and REPORT findings. The caller will fix issues. If you need to verify
something, use Read/Grep/Glob. You may use Bash ONLY for read-only commands
(e.g., git diff, git log, python -c to parse/check). NEVER use Bash for write
operations (chmod, mkdir, touch, tee, write, cp, mv, rm, etc.).**
```

This phrasing is deliberately strong. Read-only agents should still include `Bash` in their `tools` list to allow `git diff` and inline Python checks, but the prompt forbids all write operations.

Keep `Edit` and `Write` out of a read-only agent's `tools` list. If the agent also sets `memory: project`, Claude Code enables those tools anyway for its memory files, so the prompt is what holds the line. Follow the read-only clause with:

```markdown
**The one exception is your own agent memory: you may write memory files, and nothing else.**
```

---

## Memory guidance in the prompt

Don't tell the agent where or how to write memory — `memory: project` already injects the location, the file format, and the `MEMORY.md` index. Use the prompt only for what Claude Code can't know: **what is worth remembering** for this agent (e.g. "baseline row counts and schema quirks, never issue lists").

---

## Output format consistency

All clank reviewer agents use the same output structure. Maintain this format for new reviewer agents so the `/agent-review` skill can consolidate findings across multiple agents:

```
## [Lang] Code Review Summary
**Files reviewed**: [list]
**Risk level**: [LOW | MEDIUM | HIGH]

## Critical Issues (must fix)
## Improvements (should fix)
## Suggestions (nice to have)
## What's Done Well

## Review Summary
| Severity | Count | Status |
Verdict: [APPROVE | WARNING | BLOCK] — [one-line reason]
```

Severity mapping:
- **CRITICAL** — security vulnerability or data loss risk (BLOCK)
- **HIGH** — bug or significant quality issue (WARNING)
- **MEDIUM** — maintainability concern (INFO)
- **LOW** — style or minor suggestion (NOTE)

---

## Adding to the manifest

Every agent needs an `[[artifacts]]` entry in `manifest.toml`:

```toml
[[artifacts]]
id = "python-reviewer"
type = "agent"
path = "addons/python/agents/python-reviewer.md"
description = "Python specialist reviewer — FastAPI, DataFrame, async, pytest"
tags = ["python", "review"]
```

Field notes:
- `id` — stable string, never change it after the first release (uninstall depends on it)
- `type` — always `"agent"` for agent files
- `path` — relative to the clank root; must match the actual file location
- `description` — shown by `--list`; can be less detailed than the frontmatter description
- `tags` — used by `@tag:<name>` preset directives; include the language name for addon agents

---

## Checklist before committing

- [ ] Frontmatter is valid YAML (all required fields present)
- [ ] `description` is a router signal ("use when..."), not a feature summary
- [ ] `name` is unique across all agents in the manifest
- [ ] Read-only clause is included if the agent should not modify files
- [ ] No `Edit`/`Write` in `tools` if the agent is read-only; memory exception line present if `memory: project`
- [ ] Output format matches the standard reviewer structure if this is a reviewer agent
- [ ] `[[artifacts]]` entry added to `manifest.toml` with correct `path` and `tags`
- [ ] `python3 -c "import tomllib; tomllib.load(open('manifest.toml','rb'))"` passes (no TOML syntax errors)
- [ ] `./install.py --list` shows the new agent
