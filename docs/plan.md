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
- **ice-machine** carries an old, hand-maintained copy (its receipt names a
  branch, not a commit), so `--update` cannot merge there. Sync it by hand or
  re-install with `--force` when it matters.
- **MCP server versions are pinned** in the two wrappers
  (`TOOLBOX_VERSION`, `SUPABASE_MCP_VERSION`). When raising one, re-check the
  tool names against the safety hooks and the `tools` line of
  `database-reviewer`.
