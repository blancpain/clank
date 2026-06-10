#!/bin/bash
# Wrapper to start the Postgres MCP server with a connection URL from the
# project's .env / .env.local.
# Requires: npx available in PATH
#
# Usage (in .mcp.json):
#   Single database (default) — reads DB_URL:
#     "postgres": { "command": "bash", "args": [".claude/mcp/pg-mcp-wrapper.sh"] }
#
#   Multiple databases — pass the env var name per server:
#     "postgres-dev":  { "command": "bash", "args": [".claude/mcp/pg-mcp-wrapper.sh", "DB_URL_DEV"] }
#     "postgres-prod": { "command": "bash", "args": [".claude/mcp/pg-mcp-wrapper.sh", "DB_URL_PROD"] }
#
# Lookup order: .env first, then .env.local (first match wins).
# Note: @modelcontextprotocol/server-postgres is read-only by design — safe to
# point at production; writes still need an explicitly-approved psql/migration.

VAR_NAME="${1:-DB_URL}"
PROJECT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"

DB_URL=""
for ENV_FILE in "$PROJECT_DIR/.env" "$PROJECT_DIR/.env.local"; do
  if [ -z "$DB_URL" ] && [ -f "$ENV_FILE" ]; then
    DB_URL=$(awk -F= -v k="$VAR_NAME" 'index($0, k"=")==1{print substr($0, length(k)+2)}' "$ENV_FILE")
  fi
done

if [ -z "$DB_URL" ]; then
  echo "ERROR: $VAR_NAME not found in $PROJECT_DIR/.env or .env.local" >&2
  echo "Set $VAR_NAME=postgresql://user:pass@host:5432/dbname in one of those files" >&2
  exit 1
fi

exec npx -y @modelcontextprotocol/server-postgres "$DB_URL"
