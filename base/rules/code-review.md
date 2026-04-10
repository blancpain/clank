# Code Review Standards

## Purpose

Code review ensures quality, security, and maintainability before code is merged. This rule defines when and how to conduct code reviews.

## When to Review

**MANDATORY review triggers:**

- After writing or modifying code
- Before any commit to shared branches
- Before any push
- When security-sensitive code is changed (auth, database, user data)
- When architectural changes are made
- Before merging pull requests

**Pre-Review Requirements:**

Before requesting review, ensure:

- All automated checks (linting, CI) are passing
- Merge conflicts are resolved
- Branch is up to date with target branch

## Agent Usage

Use the **code-reviewer** agent for all code reviews. It covers code quality, security, Python best practices, performance, and project conventions. Launch it proactively after every meaningful code change. **Always run it in the background**.

## Review Checklist

Before marking code complete:

- [ ] Code is readable and well-named
- [ ] Functions are focused (<50 lines)
- [ ] Files are cohesive (<800 lines)
- [ ] No deep nesting (>4 levels)
- [ ] Errors are handled explicitly
- [ ] No hardcoded secrets or credentials
- [ ] No debug statements left in production code
- [ ] Tests exist for new functionality where applicable

## Review Severity Levels

| Level    | Meaning                                  | Action                             |
| -------- | ---------------------------------------- | ---------------------------------- |
| CRITICAL | Security vulnerability or data loss risk | **BLOCK** - Must fix before merge  |
| HIGH     | Bug or significant quality issue         | **WARN** - Should fix before merge |
| MEDIUM   | Maintainability concern                  | **INFO** - Consider fixing         |
| LOW      | Style or minor suggestion                | **NOTE** - Optional                |

## Review Workflow

```
1. Run git diff to understand changes
2. Check for security issues first
3. Review code quality
4. Run relevant linting/checks
5. Use code-reviewer agent for detailed review
```

## Common Issues to Catch

### Security

- Hardcoded credentials (API keys, passwords, tokens)
- SQL injection (string concatenation in queries)
- Unsafe deserialization or eval/exec
- Path traversal (unsanitized file paths)
- Secrets exposed in logs

### Code Quality

- Large functions (>50 lines) - split into smaller
- Large files (>800 lines) - extract modules
- Deep nesting (>4 levels) - use early returns
- Missing error handling - handle explicitly
- Dead code or unused imports - remove

### Performance

- N+1 queries - use JOINs or batching
- Unbounded queries - add LIMIT on user-facing endpoints
- Missing cleanup of large datasets in memory

## Approval Criteria

- **Approve**: No CRITICAL or HIGH issues
- **Warning**: Only HIGH issues (merge with caution)
- **Block**: CRITICAL issues found
