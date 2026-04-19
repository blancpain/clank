# Surgical Changes

Touch only what you must. Clean up only your own mess.

## When editing existing code

- Don't "improve" adjacent code, comments, or formatting
- Don't refactor things that aren't broken
- Match existing style, even if you would write it differently
- If you notice unrelated dead code, mention it — don't delete it

## When your changes create orphans

- Remove imports, variables, or functions that your changes made unused
- Don't remove pre-existing dead code unless asked

## The test

Every changed line should trace directly to the user's request. If a line cannot be justified that way, remove it.
