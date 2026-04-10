# Use Project Code Reviewer

When running code reviews (including those triggered by the stop hook, after completing tasks, or as part of subagent-driven development), you **must** use the project's **code-reviewer** agent (`subagent_type: "code-reviewer"`) instead of the superpowers code-reviewer (`subagent_type: "superpowers:code-reviewer"`) or any other external code review sub-agent.

The project code-reviewer has domain-specific checks (schema validation, data-pipeline integrity, framework-specific patterns, project conventions) that the generic reviewer lacks.
