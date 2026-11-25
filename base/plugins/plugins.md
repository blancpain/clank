# Claude Code Plugins

This file is a reference list of Claude Code plugins typically installed alongside clank. It is NOT automatically loaded by Claude Code — browse it manually and install the ones you want.

All of these come from the official marketplace, `claude-plugins-official`. Claude Code adds that marketplace by itself the first time you start an interactive session, so there is no `marketplace add` step. Install by name with the marketplace suffix:

```bash
claude plugin install <name>@claude-plugins-official
```

Or run `/plugin` inside Claude Code for an interactive browser.

---

### Language Servers

Install the one matching each language addon you use.

| Plugin | Description |
|--------|-------------|
| `typescript-lsp` | TypeScript/JavaScript language server — type errors, go-to-definition |
| `pyright-lsp` | Python type checking via Pyright — catches type mismatches before runtime |
| `gopls-lsp` | Go language server |
| `rust-analyzer-lsp` | Rust language server |
| `swift-lsp` | Swift language server (SourceKit-LSP) |

```bash
claude plugin install typescript-lsp@claude-plugins-official
claude plugin install pyright-lsp@claude-plugins-official
claude plugin install gopls-lsp@claude-plugins-official
claude plugin install rust-analyzer-lsp@claude-plugins-official
claude plugin install swift-lsp@claude-plugins-official
```

### Code Quality

Claude Code already ships `/code-review` (alias `/review`), `/simplify`, and `/security-review` — no plugin needed for those. clank's own `/agent-review` skill runs the project's reviewer agents instead. The plugins below add to that.

| Plugin | Description |
|--------|-------------|
| `code-simplifier` | Agent that simplifies recently modified code while preserving behavior |
| `code-review` | Multi-agent pull request review with confidence scoring |
| `pr-review-toolkit` | PR review agents for comments, tests, error handling, type design |
| `security-guidance` | Security warnings on edits and a diff review when Claude stops — complements the `security-reviewer` agent in clank |

```bash
claude plugin install code-simplifier@claude-plugins-official
claude plugin install code-review@claude-plugins-official
claude plugin install pr-review-toolkit@claude-plugins-official
claude plugin install security-guidance@claude-plugins-official
```

### Workflow

| Plugin | Description |
|--------|-------------|
| `superpowers` | General dev-workflow toolkit — TDD discipline, subagent-driven development, planning/execution skills |
| `hookify` | Create hooks conversationally — describe a behavior, get a hook generated |
| `commit-commands` | Git commit workflow — commit, push, and PR creation commands |
| `frontend-design` | Distinctive, production-grade frontend interfaces |
| `feature-dev` | Feature development workflow — exploration, architecture, and review agents |

```bash
claude plugin install superpowers@claude-plugins-official
claude plugin install hookify@claude-plugins-official
claude plugin install commit-commands@claude-plugins-official
claude plugin install frontend-design@claude-plugins-official
claude plugin install feature-dev@claude-plugins-official
```

### Docs lookup

| Plugin | Description |
|--------|-------------|
| `context7` | Context7 MCP server for live documentation lookup. Optional: clank's `docs-researcher` agent uses the `ctx7` CLI and does not need it |

```bash
claude plugin install context7@claude-plugins-official
```

---

## Not plugins

The Postgres and Supabase MCP servers that clank's database agents and hooks rely on are **not** marketplace plugins. They are installed by clank itself into `.mcp.json` — the `pg-mcp` artifact (sql preset) and the `supabase-mcp` artifact (supabase preset).
