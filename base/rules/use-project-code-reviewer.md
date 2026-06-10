# Use Project Code Reviewer

When running code reviews (including those triggered by the stop hook, after completing tasks, or as part of subagent-driven development), you **must** use the project's **code-reviewer** agent (`subagent_type: "code-reviewer"`) instead of any plugin-provided or external code-review sub-agent (e.g. `subagent_type: "superpowers:code-reviewer"`, if that plugin happens to be installed).

The project code-reviewer has domain-specific checks (schema validation, data-pipeline integrity, framework-specific patterns, project conventions) that the generic reviewer lacks.
