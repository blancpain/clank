# No comments in inline python

When using `python -c` or `python3 -c` with multiline strings, do NOT include `#` comments. The `#` character after a newline inside a quoted argument triggers a bash security heuristic that cannot be overridden by permission rules, causing an interactive prompt that blocks automated execution.

Use descriptive variable names or print statements instead of comments.
