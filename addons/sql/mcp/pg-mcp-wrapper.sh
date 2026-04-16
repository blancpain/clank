#!/bin/bash
# Wrapper to start the Postgres MCP server with DB_URL from project .env.
# Requires: npx available in PATH
# Requires: DB_URL=postgresql://... set in the project's .env file

PROJECT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"

if [ -f "$PROJECT_DIR/.env" ]; then
  DB_URL=$(awk -F= '/^DB_URL=/{print substr($0, index($0,"=")+1)}' "$PROJECT_DIR/.env")
fi

if [ -z "$DB_URL" ]; then
  echo "ERROR: DB_URL not found in $PROJECT_DIR/.env" >&2
  echo "Set DB_URL=postgresql://user:pass@host:5432/dbname in your project .env file" >&2
  exit 1
fi

exec npx -y @modelcontextprotocol/server-postgres "$DB_URL"
