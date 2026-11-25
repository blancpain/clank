#!/bin/bash
# Wrapper to start the Postgres MCP server (Google's MCP Toolbox for Databases,
# https://github.com/googleapis/mcp-toolbox) with a connection URL from the
# project's .env / .env.local.
# Requires: node + npx available in PATH
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
#
# READ-ONLY BY DEFAULT: Toolbox's `execute_sql` tool runs any SQL the database
# role allows, so this wrapper opens every session with
# default_transaction_read_only=on. That stops accidental writes; it is not a
# security boundary (a session can switch it off). For production, also connect
# with a role that can only SELECT. To allow writes through MCP, set
# READ_ONLY=false below — the companion `mcp-postgres-safety` hook still blocks
# destructive SQL and prompts on ALTER/INSERT at the tool-call layer.

READ_ONLY=true

# Pinned so a new Toolbox release cannot change the tools under every project
# at once. Raise it deliberately, after checking the tool names still match
# the safety hook and the agents' `tools` lists.
TOOLBOX_VERSION=1.18.0

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

# Toolbox takes the connection as separate POSTGRES_* variables, not a URL, and
# pastes each value verbatim into its YAML config. So split the URL with node
# (already required for npx) and JSON-encode every value: a JSON string is a
# valid quoted YAML scalar, which keeps passwords containing `#`, `:` or a
# leading `@` intact, and query parameters such as ?sslmode=require become the
# YAML mapping Toolbox expects.
{
  IFS= read -r POSTGRES_HOST
  IFS= read -r POSTGRES_PORT
  IFS= read -r POSTGRES_DATABASE
  IFS= read -r POSTGRES_USER
  IFS= read -r POSTGRES_PASSWORD
  IFS= read -r POSTGRES_QUERY_PARAMS
} < <(node -e '
  const u = new URL(process.argv[1]);
  const params = u.searchParams;
  if (process.argv[2] === "true" && !params.has("default_transaction_read_only")) {
    params.set("default_transaction_read_only", "on");
  }
  const quote = (s) => JSON.stringify(decodeURIComponent(s));
  console.log([
    quote(u.hostname.replace(/^\[|\]$/g, "")),
    u.port || "5432",
    quote(u.pathname.slice(1)),
    quote(u.username),
    quote(u.password),
    params.size ? JSON.stringify(Object.fromEntries(params)) : "",
  ].join("\n"));
' "$DB_URL" "$READ_ONLY" 2>/dev/null)

if [ -z "$POSTGRES_HOST" ] || [ "$POSTGRES_DATABASE" = '""' ] || [ "$POSTGRES_USER" = '""' ]; then
  echo "ERROR: could not parse $VAR_NAME as a Postgres URL" >&2
  echo "Expected $VAR_NAME=postgresql://user:pass@host:5432/dbname" >&2
  exit 1
fi

export POSTGRES_HOST POSTGRES_PORT POSTGRES_DATABASE POSTGRES_USER POSTGRES_PASSWORD POSTGRES_QUERY_PARAMS
exec npx -y "@toolbox-sdk/server@$TOOLBOX_VERSION" --prebuilt=postgres --stdio
