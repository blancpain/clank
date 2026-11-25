#!/bin/bash
# Prints one line for each pinned MCP server that has a newer release on npm:
#   <package> <pinned version> <latest version>
# Prints nothing when every pin is current.
set -euo pipefail
cd "$(dirname "$0")/../.."

check() { # <wrapper> <variable> <npm package>
  local pinned latest
  pinned=$(sed -n "s/^$2=//p" "$1")
  if [ -z "$pinned" ]; then
    echo "ERROR: $2 is not set in $1" >&2
    exit 1
  fi
  latest=$(npm view "$3" version)
  if [ "$pinned" != "$latest" ]; then
    echo "$3 $pinned $latest"
  fi
}

check addons/sql/mcp/pg-mcp-wrapper.sh TOOLBOX_VERSION @toolbox-sdk/server
check addons/supabase/mcp/supabase-mcp-wrapper.sh SUPABASE_MCP_VERSION @supabase/mcp-server-supabase
