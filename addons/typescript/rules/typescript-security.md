# TypeScript Security

Apply these TypeScript/JavaScript-specific security rules in addition to the general security guidelines.

## Never Hardcode Secrets

API keys, tokens, and passwords must come from environment variables — never from source:

```typescript
// WRONG
const client = new OpenAI({ apiKey: 'sk-proj-xxxxx' });

// CORRECT
const apiKey = process.env.OPENAI_API_KEY;
if (!apiKey) throw new Error('OPENAI_API_KEY is not set');
const client = new OpenAI({ apiKey });
```

Validate all required env vars at startup, not at first use. This fails fast and prevents partial initialization.

## XSS — `dangerouslySetInnerHTML` and `innerHTML`

Never assign unsanitized strings to `innerHTML` or `dangerouslySetInnerHTML`:

```typescript
// WRONG — injects attacker-controlled HTML
element.innerHTML = userInput;
<div dangerouslySetInnerHTML={{ __html: comment.body }} />

// CORRECT — sanitize first
import DOMPurify from 'dompurify';
element.innerHTML = DOMPurify.sanitize(userInput);
<div dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(comment.body) }} />
```

If you need to render rich text from users, use an allowlist-based sanitizer (DOMPurify, sanitize-html) or render Markdown to a safe AST instead.

## No `eval()` or `new Function()`

Both execute arbitrary code strings. There is almost never a valid use case:

```typescript
// WRONG
eval(userProvidedCode);
new Function('return ' + expression)();

// If you need dynamic computation: use a safe expression parser (e.g., mathjs, expr-eval)
// or redesign the feature to use data, not code
```

## Prototype Pollution

Never spread or assign untrusted objects without validation:

```typescript
// WRONG — attacker sends {"__proto__": {"admin": true}}
Object.assign(config, JSON.parse(userInput));

// CORRECT — validate against a schema first
import { z } from 'zod';
const schema = z.object({ theme: z.enum(['light', 'dark']) });
const parsed = schema.parse(JSON.parse(userInput));
Object.assign(config, parsed);
```

Also flag `merge(target, userInput)` from utility libraries that recursively copy without protection.

## ReDoS — Catastrophic Backtracking

Regex patterns with nested quantifiers on user-controlled strings cause exponential backtracking (Denial of Service):

```typescript
// WRONG — catastrophic on input like 'aaaaaaaaaaaaaaaaab'
const pattern = /(a+)+$/;
pattern.test(userInput);

// CORRECT — atomic groups or possessive quantifiers (or redesign)
// Consider using a linear-time regex library (re2) for untrusted inputs
```

Flag patterns like `(x+)+`, `(x|x)+`, `(a*)*` applied to user data.

## `postMessage` Origin Verification

Event handlers that listen to `message` must verify the sender's origin:

```typescript
// WRONG — processes messages from any window
window.addEventListener('message', (event) => {
  processCommand(event.data);
});

// CORRECT
window.addEventListener('message', (event) => {
  if (event.origin !== 'https://trusted.example.com') return;
  processCommand(event.data);
});
```

## `localStorage` is Not a Secret Store

`localStorage` is accessible to any JavaScript on the page — including injected scripts from XSS:

```typescript
// WRONG — tokens in localStorage are exfiltrable via XSS
localStorage.setItem('access_token', token);

// CORRECT — use httpOnly cookies managed by the server
// Tokens set as httpOnly cookies are invisible to JavaScript entirely
```

PII and credentials must not be stored in `localStorage` or `sessionStorage`. Ephemeral UI state (theme, sidebar open) is fine.

## Input Validation at Boundaries

Validate and type all external data — API responses, form inputs, URL params — before using it in business logic. Use Zod or a similar schema library:

```typescript
import { z } from 'zod';

const UserSchema = z.object({
  id: z.string().uuid(),
  email: z.string().email(),
  role: z.enum(['admin', 'viewer']),
});

// At the API response boundary
const user = UserSchema.parse(await res.json());
// user is now fully typed and validated — no unknown fields slip through
```

Never pass raw `JSON.parse()` output into business logic without validation.

## Path Traversal in Node.js

User-controlled file paths must be sanitized before use:

```typescript
import path from 'node:path';

// WRONG — attacker can read /etc/passwd with path='../../../etc/passwd'
const file = fs.readFileSync(path.join(uploadsDir, userInput));

// CORRECT — verify the resolved path is inside the allowed directory
const resolved = path.resolve(uploadsDir, userInput);
if (!resolved.startsWith(path.resolve(uploadsDir))) {
  throw new Error('Path traversal detected');
}
const file = fs.readFileSync(resolved);
```

## Content Security Policy

New projects should configure a CSP header. Avoid `unsafe-inline` and `unsafe-eval` in script-src. If a framework generates these for you (Next.js `next.config.js` headers), verify they are restrictive.

## Dependency Hygiene

- Run `pnpm audit` / `npm audit` in CI and block on high/critical advisories
- Pin dependency versions (no `^` or `~` for security-critical packages)
- Review new dependencies before adding: check download count, maintainer activity, and known CVEs
