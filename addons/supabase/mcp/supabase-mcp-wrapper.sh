#!/bin/bash
# Wrapper to start the Supabase MCP server with credentials from project .env.
# Requires: npx available in PATH
# Requires: SUPABASE_ACCESS_TOKEN and SUPABASE_PROJECT_REF set in the project's .env file
#
# Starts in --read-only mode by default. If you need write access (e.g. running
# mcp__supabase__apply_migration), remove the --read-only flag below. Note that
# the companion `mcp-supabase-safety` hook still blocks destructive SQL at the
# tool-call layer even when the server is writable.

PROJECT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"

if [ -f "$PROJECT_DIR/.env" ]; then
  SUPABASE_ACCESS_TOKEN=$(awk -F= '/^SUPABASE_ACCESS_TOKEN=/{print substr($0, index($0,"=")+1)}' "$PROJECT_DIR/.env")
  SUPABASE_PROJECT_REF=$(awk -F= '/^SUPABASE_PROJECT_REF=/{print substr($0, index($0,"=")+1)}' "$PROJECT_DIR/.env")
fi

if [ -z "$SUPABASE_ACCESS_TOKEN" ]; then
  echo "ERROR: SUPABASE_ACCESS_TOKEN not found in $PROJECT_DIR/.env" >&2
  echo "Create a personal access token at https://supabase.com/dashboard/account/tokens" >&2
  echo "Then add SUPABASE_ACCESS_TOKEN=<token> to your project .env file" >&2
  exit 1
fi

if [ -z "$SUPABASE_PROJECT_REF" ]; then
  echo "ERROR: SUPABASE_PROJECT_REF not found in $PROJECT_DIR/.env" >&2
  echo "Find your project ref at https://supabase.com/dashboard/project/_/settings/general" >&2
  echo "Then add SUPABASE_PROJECT_REF=<ref> to your project .env file" >&2
  exit 1
fi

export SUPABASE_ACCESS_TOKEN
exec npx -y @supabase/mcp-server-supabase --project-ref "$SUPABASE_PROJECT_REF" --read-only
