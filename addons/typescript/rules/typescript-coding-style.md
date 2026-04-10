# TypeScript Coding Style

Follow these TypeScript-specific conventions in addition to the general coding style guidelines.

## Standards

- Use **TypeScript strict mode** (`"strict": true` in `tsconfig.json`). Also enable `noUncheckedIndexedAccess` and `exactOptionalPropertyTypes` where feasible.
- Use **biome** for linting and formatting (preferred over ESLint + Prettier separately).
- Target **ES2022+** — use `structuredClone`, `Object.hasOwn`, `Array.at()`, and `at()` instead of older polyfill equivalents.

## Naming

- `camelCase` for variables, functions, and methods
- `PascalCase` for types, interfaces, classes, and components
- `SCREAMING_SNAKE_CASE` for module-level constants
- `_leadingUnderscore` only for genuinely private class members when private fields (`#field`) are not suitable
- Booleans: prefix with `is`, `has`, `can`, `should` — e.g. `isLoading`, `hasError`
- Event handlers: prefix with `on` or `handle` — e.g. `onSubmit`, `handleClick`

## Types vs Interfaces

Prefer `interface` for object shapes that may be extended or implemented; use `type` for unions, intersections, tuples, and aliases:

```typescript
// Prefer interface for extendable shapes
interface User {
  readonly id: string;
  name: string;
  email: string;
}

// Use type for unions and computed shapes
type Status = 'idle' | 'loading' | 'success' | 'error';
type Nullable<T> = T | null;
type UserWithRole = User & { role: 'admin' | 'viewer' };
```

## No `any`

Never use `any`. When the type is genuinely unknown at write time, use `unknown` and narrow it before use:

```typescript
// WRONG
function parse(input: any): any { ... }

// CORRECT
function parse(input: unknown): Result<ParsedData, string> {
  if (!isValidInput(input)) return { ok: false, error: 'invalid' };
  return { ok: true, value: input as ParsedData };
}
```

## Prefer `satisfies` for Literal Narrowing

Use `satisfies` when you want type-checking without widening the type:

```typescript
// WRONG: widens to Record<string, string>
const config: Record<string, string> = { host: 'localhost', port: '5432' };

// CORRECT: keeps literal types, still checked against the shape
const config = { host: 'localhost', port: '5432' } satisfies Record<string, string>;
```

## `readonly` on Immutable Shapes

Mark fields `readonly` on types that represent immutable data (props, config, domain entities):

```typescript
interface Config {
  readonly host: string;
  readonly port: number;
  readonly ssl: boolean;
}
```

## Explicit Return Types on Exported Functions

Inferred return types on public API functions are fragile — add explicit annotations:

```typescript
// WRONG: inferred return type changes silently when implementation changes
export function getUser(id: string) {
  return db.users.find(id);
}

// CORRECT
export function getUser(id: string): Promise<User | null> {
  return db.users.find(id);
}
```

## Null Safety

Prefer explicit `null | undefined` over optional chaining everywhere. When accessing a value that might be undefined, assert with a type guard rather than `!`:

```typescript
// WRONG
const name = user!.name;

// CORRECT
if (!user) throw new Error('user is required');
const name = user.name;
```

## Imports and Barrel Exports

- Group imports: external packages → internal modules → types (with a blank line between groups)
- Use `import type` for type-only imports — helps tree-shakers and avoids circular deps at runtime
- Barrel files (`index.ts`) are fine for public APIs but avoid deeply nested re-exports that obscure where things live
- Prefer named exports over default exports for utilities and components

```typescript
import { useState, useCallback } from 'react';

import { fetchUser } from '@/lib/api';
import { formatDate } from '@/lib/utils';

import type { User } from '@/types';
```

## File Organization

- One primary export per file for components (the component name matches the filename)
- Co-locate closely related helpers in the same file; extract to a new file when a helper grows beyond ~30 lines or is reused
- Keep files under ~300 lines; extract subcomponents or hooks when files grow beyond this
- Test files live adjacent to source: `user.ts` → `user.test.ts`

## JSDoc for Public APIs

Public functions and types in shared libraries need JSDoc — not every internal helper, just the public contract:

```typescript
/**
 * Fetches a user by ID from the database.
 * Returns null if the user does not exist.
 * Throws on network or database errors.
 */
export async function getUser(id: string): Promise<User | null> { ... }
```

## Console Statements

No `console.log` in production code. Use a structured logger (`pino`, `winston`) or the framework's logging primitives. In frontend code, `console.error` is acceptable at error boundaries; all others should be removed before commit.

## Dependency Management

Use **pnpm** or **npm** workspaces for monorepos. Pin exact versions for security-critical dependencies. Run `pnpm audit` or `npm audit` in CI.
