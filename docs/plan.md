# Plan

What's being worked on and what's queued. Read this before starting work;
update it when priorities shift or items ship (move shipped items to
`CHANGELOG.md`).

## Now

Nothing is in flight.

## Queued

- (nothing queued — file ideas here as they come up)

## Later / external

- **Updating a project:** run `./install.py --update` from the project (see
  `docs/install.md`, "Update workflow"). horses, sisu, mangify-ios and mangify
  are on tracked receipts as of 2026-11-25, so retired artifacts and local
  edits are handled from here on.
- **ice-machine** predates clank. Seven artifacts it shares with clank (the
  hooks `review-before-commit`, `file-safety` and `ruff`, and the rules
  `code-review`, `long-running-scripts`, `use-project-code-reviewer`,
  `update-agent-memory`) are on a tracked receipt and follow `--update`. Its
  other agents, hooks, skills and the Postgres wrapper are its own versions
  under different file names; they are not in the receipt and stay
  hand-maintained. Its Biome and svelte-check hooks were not compared against
  clank's (the frontend packages are only installed on the mini), and its
  wrapper opens an SSH tunnel that clank's does not. Moving them onto clank's versions would be
  a migration, file by file, not an update.
- **MCP server versions are pinned** in the two wrappers
  (`TOOLBOX_VERSION`, `SUPABASE_MCP_VERSION`). The weekly `mcp-pins` workflow
  opens an issue when a newer release is out; the issue lists the steps
  (re-check tool names against the safety hooks and the `tools` line of
  `database-reviewer`, then `--update` each project).
