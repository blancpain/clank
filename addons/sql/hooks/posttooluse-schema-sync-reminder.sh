#!/bin/bash
# PostToolUse hook: remind Claude to update the schema reference file
# (`.claude/skills/querying-db/schema.txt`) when a schema-defining file is edited.
#
# Works with the `querying-db` skill, which reads `schema.txt` before every query.
# If the reference drifts from the real schema, queries start failing silently —
# this hook fires when a schema source is modified so the reference gets updated
# in the same turn.
#
# --- Customization ---
# SCHEMA_PATTERNS below controls which files trigger the reminder. The defaults
# cover common layouts (SQLAlchemy/Django models, raw DDL, Prisma, Rails schema,
# migration directories). Add project-specific paths as needed — e.g.
#   */myapp/db/tables.py
# Globs use bash extglob-style matching against the tool's `file_path` input.

SCHEMA_PATTERNS=(
  '*/schema.py'
  '*/schema.sql'
  '*/models.py'
  '*/models/*.py'
  '*/migrations/*.sql'
  '*/migrations/*.py'
  '*/alembic/versions/*.py'
  '*/prisma/schema.prisma'
  '*/db/schema.rb'
  '*/database/schema.*'
)

command -v jq >/dev/null 2>&1 || exit 0

INPUT=$(cat 2>/dev/null) || exit 0
[ -z "$INPUT" ] && exit 0

# Fast path: skip jq entirely if the payload can't possibly reference a schema
# file. Must stay in sync with SCHEMA_PATTERNS above — any new pattern needs a
# matching token here.
echo "$INPUT" | grep -qiE 'schema|migration|models|prisma' || exit 0

FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_response.filePath // empty')
[ -z "$FILE_PATH" ] && exit 0

MATCHED=0
for pattern in "${SCHEMA_PATTERNS[@]}"; do
  # shellcheck disable=SC2053
  if [[ "$FILE_PATH" == $pattern ]]; then
    MATCHED=1
    break
  fi
done

[ "$MATCHED" -eq 0 ] && exit 0

# The hook is paired with the `querying-db` skill. If the skill isn't installed
# in this project, silently pass — the user opted out of the schema-reference
# pattern and doesn't want to be nagged about it.
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
SKILL_DIR="$PROJECT_DIR/.claude/skills/querying-db"
SCHEMA_REF="$SKILL_DIR/schema.txt"

[ -d "$SKILL_DIR" ] || exit 0

if [ ! -f "$SCHEMA_REF" ]; then
  jq -n --arg file "$FILE_PATH" --arg ref "$SCHEMA_REF" '{
    decision: "block",
    reason: ("Schema source \($file) was just modified, but the querying-db skill reference file \($ref) does not exist yet.\n\nCreate it now so the schema stays queryable:\n  1. Copy .claude/skills/querying-db/schema.txt.template → schema.txt\n  2. Fill it in from the file you just edited (tables, columns, enums, joins, indexes, gotchas).\n\nIf you do not intend to use the querying-db skill, remove the schema-sync-reminder hook from .claude/settings.json to silence this message.")
  }'
  exit 0
fi

jq -n --arg file "$FILE_PATH" --arg ref "$SCHEMA_REF" '{
  decision: "block",
  reason: ("Schema source \($file) was just modified. You MUST also update \($ref) to reflect any new or changed tables, columns, indexes, constraints, or enum values.\n\nRead schema.txt, diff against the change you just made, and update it in the same turn. Stale schema references cause queries to fail silently against the real DB.")
}'

exit 0
