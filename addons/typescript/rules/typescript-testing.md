# TypeScript Testing

Follow these TypeScript-specific testing conventions in addition to the general testing guidelines.

## Test Runner

- Use **Jest** as the test runner. In existing projects, keep whatever runner is already configured rather than migrating.
- Use **React Testing Library** (RTL) for component tests — test behavior from the user's perspective, not implementation details.
- Use **Playwright** for E2E tests of critical user flows.

## File Naming

- Unit/integration: `feature.test.ts` or `feature.spec.ts` adjacent to source
- E2E: `feature.e2e.ts` in a top-level `e2e/` directory
- Test utilities and fixtures: `__fixtures__/` or `__mocks__/` subdirectories

## Test Structure — AAA

Every test follows Arrange / Act / Assert:

```typescript
it('returns null when user does not exist', async () => {
  // Arrange
  const db = createTestDb();
  const userId = 'nonexistent-id';

  // Act
  const result = await getUser(db, userId);

  // Assert
  expect(result).toBeNull();
});
```

## Descriptive Names

Name tests as sentences that describe behavior. The failure message should read like a requirement:

```typescript
// WRONG
it('test getUser', () => { ... });

// CORRECT
it('returns the user when the id exists in the database', async () => { ... });
it('throws UserNotFoundError when the id does not exist', async () => { ... });
```

## Typing in Tests

Tests are still TypeScript — do not use `any` to silence type errors in test code. If a helper needs to accept any shape, use `unknown` and narrow it:

```typescript
// WRONG
const result = await handler(request as any);

// CORRECT
const result = await handler(createMockRequest({ method: 'GET', path: '/users' }));
```

## Mocking with `jest.mock`

- Mock at the module boundary, not deep inside functions
- Use `jest.fn()` with explicit return types so callers are type-safe
- Reset mocks between tests with `jest.clearAllMocks()` in `beforeEach` or `afterEach`

```typescript
import * as api from '@/lib/api';

jest.mock('@/lib/api');

beforeEach(() => {
  jest.clearAllMocks();
});

it('calls the API with the correct user id', async () => {
  jest.mocked(api.fetchUser).mockResolvedValue({ id: '1', name: 'Alice' });

  const result = await getDisplayName('1');

  expect(api.fetchUser).toHaveBeenCalledWith('1');
  expect(result).toBe('Alice');
});
```

## React Testing Library Discipline

- Query by role, label, or test id — never by CSS class or DOM structure
- Prefer `userEvent` over `fireEvent` for realistic interaction simulation
- Wrap state updates in `act()` only when RTL doesn't do it automatically (rare)
- Use `waitFor` or `findBy*` for async assertions, not arbitrary `setTimeout`

```typescript
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

it('submits the form when the user clicks Save', async () => {
  const user = userEvent.setup();
  const onSubmit = jest.fn();

  render(<EditForm onSubmit={onSubmit} />);

  await user.type(screen.getByLabelText('Name'), 'Alice');
  await user.click(screen.getByRole('button', { name: /save/i }));

  expect(onSubmit).toHaveBeenCalledWith({ name: 'Alice' });
});
```

## Async Tests

Always `await` async assertions. Use `expect.assertions(n)` in tests where you expect a rejection, to guard against the test passing vacuously:

```typescript
it('throws when the token is expired', async () => {
  expect.assertions(1);
  await expect(validateToken('expired')).rejects.toThrow('Token expired');
});
```

## Coverage Targets

- Aim for **>80% line coverage** on business logic modules
- Coverage on UI components is lower priority — focus on critical paths
- Do NOT write tests purely to hit coverage — test behavior, not lines
- Exclude generated files, type declarations, and migration scripts from coverage

## What NOT to Test

- Implementation details (internal state, private methods)
- Third-party library behavior
- TypeScript types themselves (the compiler enforces those)
- Trivial getters/setters with no logic
