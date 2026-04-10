# TypeScript Patterns

Apply these TypeScript-specific idioms and patterns for correctness and maintainability.

## Discriminated Unions

Model variants as discriminated unions rather than optional fields or inheritance. Exhaustive switches are then enforced by the compiler:

```typescript
// WRONG — optional fields don't enforce which combination is valid
interface Response {
  data?: User;
  error?: string;
  loading?: boolean;
}

// CORRECT — each state is explicit and mutually exclusive
type Response =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'success'; data: User }
  | { status: 'error'; error: string };
```

## Exhaustive Switches with `never`

When switching over a discriminated union, use a `never` assertion in the default case to catch unhandled variants at compile time:

```typescript
function render(response: Response): string {
  switch (response.status) {
    case 'idle':    return 'Ready';
    case 'loading': return 'Loading...';
    case 'success': return response.data.name;
    case 'error':   return `Error: ${response.error}`;
    default: {
      const exhausted: never = response;
      throw new Error(`Unhandled status: ${JSON.stringify(exhausted)}`);
    }
  }
}
```

If you add a new variant to the union, the compiler will error at the `never` assertion until you handle it.

## Branded Types

Use branded types to prevent accidental mixing of structurally identical primitives:

```typescript
type UserId = string & { readonly __brand: 'UserId' };
type GameId = string & { readonly __brand: 'GameId' };

function createUserId(id: string): UserId {
  return id as UserId;
}

// Now passing a GameId where a UserId is expected is a compile error
function getUser(id: UserId): Promise<User> { ... }
```

Use this for IDs, currency amounts, validated strings (email, URL), and units (meters vs. feet).

## Type Predicates

Write explicit type guards when narrowing `unknown` or union types:

```typescript
function isUser(value: unknown): value is User {
  return (
    typeof value === 'object' &&
    value !== null &&
    'id' in value &&
    typeof (value as User).id === 'string'
  );
}

// Usage
const data: unknown = await fetchJSON('/api/user');
if (!isUser(data)) throw new Error('Unexpected response shape');
console.log(data.name); // data is now User
```

## Result / Either Pattern

For operations with expected failure modes, use a Result type instead of throwing:

```typescript
type Result<T, E = string> =
  | { ok: true; value: T }
  | { ok: false; error: E };

async function parseConfig(raw: string): Promise<Result<Config>> {
  try {
    const parsed = JSON.parse(raw);
    const validated = ConfigSchema.safeParse(parsed);
    if (!validated.success) {
      return { ok: false, error: validated.error.message };
    }
    return { ok: true, value: validated.data };
  } catch {
    return { ok: false, error: 'Invalid JSON' };
  }
}

// Caller handles both cases explicitly
const result = await parseConfig(raw);
if (!result.ok) {
  console.error(result.error);
  return;
}
doSomethingWith(result.value);
```

Use `Result` for validation, parsing, and external I/O. Continue to `throw` for truly unexpected/programmer errors.

## Zod Validation at Boundaries

Parse and validate all external data (API responses, env vars, user input) with Zod at the entry point:

```typescript
import { z } from 'zod';

const EnvSchema = z.object({
  DATABASE_URL: z.string().url(),
  PORT: z.coerce.number().int().min(1024).max(65535).default(3000),
  NODE_ENV: z.enum(['development', 'production', 'test']).default('development'),
});

export const env = EnvSchema.parse(process.env);
// env is fully typed — no undefined, no string where number expected
```

For API responses, define schemas alongside the fetch call:

```typescript
const UserSchema = z.object({
  id: z.string().uuid(),
  name: z.string().min(1),
  createdAt: z.coerce.date(),
});

const res = await fetch('/api/user/1');
const user = UserSchema.parse(await res.json());
```

## Immutable Updates

Use spread for immutable object updates; `Array.prototype.with()` for immutable array element replacement (ES2023):

```typescript
// Objects
const updated = { ...user, name: 'Alice' };

// Arrays — remove at index
const removed = [...items.slice(0, index), ...items.slice(index + 1)];

// Arrays — replace at index (ES2023)
const replaced = items.with(index, newItem);
```

Avoid mutating objects or arrays passed in as arguments — return new values.

## Utility Types

Use built-in utility types instead of manually constructing equivalent shapes:

```typescript
type Partial<T>       // all fields optional
type Required<T>      // all fields required
type Readonly<T>      // all fields readonly
type Pick<T, K>       // subset of fields
type Omit<T, K>       // all fields except K
type ReturnType<F>    // infer return type of a function
type Parameters<F>    // infer parameter tuple of a function
type Awaited<T>       // unwrap Promise<T> -> T
```

Avoid reaching for complex conditional types when a composition of utility types achieves the same result more readably.

## Avoid Redundant Type Annotations

Let TypeScript infer where inference is unambiguous; annotate at public API boundaries and when inference would be too wide:

```typescript
// WRONG — redundant, inference gives the same type
const count: number = 0;
const items: string[] = ['a', 'b'];

// CORRECT — inference is fine here
const count = 0;
const items = ['a', 'b'];

// REQUIRED — public API boundary
export function sum(values: number[]): number { ... }
```
