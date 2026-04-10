# Claude Code Plugins

This file is a reference list of Claude Code plugins typically installed alongside clank. It is NOT automatically loaded by Claude Code — browse it manually and install the ones you want via `claude plugin install`.

## Adding the Official Plugin Marketplace

Before installing individual plugins, add the official marketplace:

```bash
claude plugin marketplace add https://github.com/anthropics/claude-plugins-official
```

---

### Language Servers & Typing

| Plugin | Description |
|--------|-------------|
| `typescript-lsp` | TypeScript language intelligence — type errors, go-to-definition, completions |
| `pyright-lsp` | Python type checking via Pyright — catches type mismatches before runtime |

```bash
claude plugin install typescript-lsp
claude plugin install pyright-lsp
```

### Code Quality / Simplification

| Plugin | Description |
|--------|-------------|
| `code-simplifier` | Refactor and simplify code — provides the `/simplify` slash command |
| `code-review` | Code review commands — complements the `code-reviewer` agent in clank |
| `pr-review-toolkit` | PR review automation — review pull requests from the CLI |
| `security-guidance` | Security checks — complements the `security-reviewer` agent in clank |

```bash
claude plugin install code-simplifier
claude plugin install code-review
claude plugin install pr-review-toolkit
claude plugin install security-guidance
```

### Workflow

| Plugin | Description |
|--------|-------------|
| `hookify` | Create hooks conversationally — describe a behavior, get a hook generated |
| `commit-commands` | Git commit workflow — opinionated commit message generation |
| `frontend-design` | UI design patterns — component scaffolding, accessibility, responsiveness |
| `feature-dev` | Feature development workflow — planning, scaffolding, and verification |

```bash
claude plugin install hookify
claude plugin install commit-commands
claude plugin install frontend-design
claude plugin install feature-dev
```

### Search / Docs

| Plugin | Description |
|--------|-------------|
| `mgrep` | Enhanced grep — better than ripgrep for some large-codebase search patterns |
| `context7` | Live documentation lookup — companion to the `docs-researcher` agent in clank |

```bash
claude plugin install mgrep
claude plugin install context7
```

### MCP Servers

MCP servers extend Claude Code with external tool access. These are required by specific clank agents.

| Plugin | Description |
|--------|-------------|
| `postgres` | PostgreSQL MCP server — required by the `database-reviewer` agent and the `sql` addon |
| `context7` | Context7 MCP server — used by the `docs-researcher` agent for live docs lookup |

```bash
claude plugin install postgres
claude plugin install context7
```

---

> **Install order:** Run `marketplace add` first (once), then `plugin install` by name for each plugin you want. See the `/plugins` slash command in Claude Code for an interactive browser.
