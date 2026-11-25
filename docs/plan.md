# Plan

What's being worked on and what's queued. Read this before starting work;
update it when priorities shift or items ship (move shipped items to
`CHANGELOG.md`).

## Now

Nothing is in flight.

## Queued

- (nothing queued — file ideas here as they come up)

## Later / external

- **Downstream cleanup after the 2026-11-25 audit.** The installer has no
  notion of retired artifacts, so a re-install leaves these behind in projects
  that already have them; delete by hand (and drop the ids from
  `.claude/.clank-installed.json` if listed): `.claude/rules/agents.md`,
  `.claude/rules/no-inline-comments.md`,
  `.claude/rules/executing-actions-with-care.md`, `.claude/skills/review/`
  (replaced by `agent-review`). Re-install to pick up the fixed hooks and
  path-scoped rules.
- **pg-mcp moved to MCP Toolbox (2026-11-25).** Re-installing the sql preset
  swaps the wrapper in place; `.mcp.json` and `DB_URL` in `.env` need no
  change. The query tool is now `mcp__postgres__execute_sql`, so update any
  project-local prompts or permission rules that name `mcp__postgres__query`.
  The old `mcp__postgres[a-z0-9-]*__query` hook entry stays in
  `.claude/settings.json` (it never matches now; delete it by hand).
- Re-run the installer across existing projects so they pick up the
  project-docs convention (rule + canonical-first pickup/handoff). Done for
  sisu (2026-06-12); other repos get it on their next clank install.
- New `addons/swift/rules/release-discipline.md` + `ios-run` §2a (2026-06-16):
  Swift projects pick them up on their next clank install. Synced manually into
  sisu (PR #34).
