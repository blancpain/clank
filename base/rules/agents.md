# Agent Orchestration

## Available Agents

Located in `~/.claude/agents/`:

| Agent | Purpose | When to Use |
|-------|---------|-------------|
| code-reviewer | Generic code review | After writing or modifying any code |
| security-reviewer | OWASP-focused security review | Any change touching auth/crypto/input handling/SQL |
| database-reviewer | Postgres integrity audit | Schema changes, suspected data gaps, after migrations |
| docs-researcher | Fetch library/framework docs | New library, version migration, unfamiliar API |
| doc-updater | Check docs vs. recent code | After feature work, API changes, config changes |

> Language-specific reviewers (python-reviewer, typescript-reviewer, etc.) may be present if their addon is installed — use them alongside code-reviewer for language-specific depth.

## Immediate Agent Usage

No user prompt needed — invoke these automatically:

1. Code just written/modified → **code-reviewer**
2. Auth/crypto/input-handling change → **security-reviewer** (in parallel with code-reviewer)
3. Database integrity concern, schema change, post-migration → **database-reviewer**
4. New library question or version migration → **docs-researcher**
5. After significant feature work → **doc-updater**

## Parallel Task Execution

Dispatch agents in parallel when their work is independent. Multiple Task tool uses in one assistant message:

```markdown
# GOOD: Parallel execution
Launch 2 agents in parallel:
1. Agent 1: code-reviewer on the diff
2. Agent 2: security-reviewer on the auth changes

# BAD: Sequential when unnecessary
First code-reviewer, then wait, then security-reviewer
```

## Multi-Perspective Analysis

For complex problems, use split-role subagents in parallel:
- Factual reviewer
- Senior engineer
- Security expert
- Consistency reviewer
