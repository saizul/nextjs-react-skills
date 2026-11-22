---
name: react-testing
description: Write and fix tests for React and Next.js with React Testing Library plus Vitest or Jest - project setup (jsdom, @vitejs/plugin-react, next/jest, jest-dom, user-event), accessible queries (getByRole, getByLabelText), async UI with findBy and waitFor, user-event interactions, mocking next/navigation, fetch with MSW, Server Actions and modules, testing hooks with renderHook, forms with useActionState, fake timers, and when to use Playwright instead (async Server Components, full flows). Includes a script that detects the test setup, lists untested components and hooks ranked by risk, and flags test smells such as .only, sleeps, container.querySelector and snapshot-only tests. Use when the user asks to add tests, set up Vitest or Jest in Next.js, fix flaky or failing React tests, "test this component/hook/form", mock useRouter, or find what is not tested.
license: MIT
compatibility: React 18-19, Next.js 13-16, Vitest 3-4 or Jest 29-30, Testing Library 16. Script needs Python 3.8+ only.
metadata:
  author: Saizul Amin
  version: "0.1.0"
---

# React testing

Test behaviour the user can see: render, interact like a user, assert on what is on screen.
Query by role and label, not by class names or test ids. Unit/integration tests with
Testing Library for components and hooks; Playwright for async Server Components and
end-to-end flows.

Paths below are relative to this skill's folder (in Claude Code: `${CLAUDE_SKILL_DIR}`).

## When to use

- "Add tests for this component / hook / form", "what should I test?"
- Setting up Vitest or Jest in a Next.js project
- Flaky tests, "not wrapped in act(...)" warnings, "unable to find role" errors
- Mocking `useRouter`, `usePathname`, `fetch`, Server Actions, environment variables
- Finding untested components before a refactor

## When not to use

- Load or performance testing
- Visual regression testing (use Playwright screenshots, Chromatic or similar)
- Backend-only code with no React (plain unit tests; this skill's mocking notes still help)

## Workflow

1. **Inspect the setup (read-only).**
   ```bash
   python3 scripts/find_test_gaps.py .
   python3 scripts/find_test_gaps.py . --json --top 50
   python3 scripts/find_test_gaps.py . --fail-on medium   # CI gate on setup problems
   ```
   It prints the detected runner and libraries, untested components/hooks ranked by risk
   (size, handlers, hooks), and smells: TST010 `.only`, TST011 skipped tests, TST012 real
   sleeps, TST013 `container.querySelector`, TST014 `fireEvent` with user-event installed,
   TST015 snapshot-only files, TST016 heavy `getByTestId`. Default exit 1 only on `.only`.
2. **Fix the setup if needed** with [references/setup.md](references/setup.md): Vitest
   (recommended for new projects) or Jest via `next/jest`; jsdom environment; setup file
   importing jest-dom matchers; path aliases. Show the install command and config diff;
   let the user run installs.
3. **Choose what to test.** Start with the top of the risk list and with code that has
   logic: forms, conditional rendering, hooks with state, reducers, formatting helpers. For
   async Server Components and multi-page flows (login, checkout) write Playwright tests.
4. **Write tests** using [references/recipes.md](references/recipes.md):
   - `render` -> `userEvent.setup()` -> `await user.click(screen.getByRole(...))` -> `expect`
   - `findBy*` for things that appear asynchronously; `waitFor` only for non-DOM assertions
   - mock at the boundary: `next/navigation`, network (MSW), Server Actions module
   - one behaviour per test, named as a sentence ("shows an error when the email is invalid")
5. **Run the tests** (`npx vitest run` or `npx jest`) and iterate until green. When a test
   fails, read the Testing Library DOM dump before changing the query; prefer fixing the
   component's accessibility (missing label, role) over switching to `getByTestId`.
6. **Remove smells** the script reported (`.only`, sleeps, snapshot-only tests) and re-run it.

## Output

```
Test setup: vitest 4, jsdom, RTL 16, user-event, jest-dom   (ok)
Untested (top 5 by risk): components/CheckoutForm.tsx (score 18), hooks/useCart.ts (12), ...
Added
- components/CheckoutForm.test.tsx: renders fields, validates email, submits, shows server error
- hooks/useCart.test.ts: add/remove/quantity, persists to localStorage
Fixed smells: removed it.only in Header.test.tsx; replaced setTimeout sleep with findByText
Result: 23 passed (1.8 s)
```

## Query priority

1. `getByRole(role, { name })` 2. `getByLabelText` 3. `getByPlaceholderText`
4. `getByText` 5. `getByDisplayValue` 6. `getByAltText` / `getByTitle` 7. `getByTestId` (last resort)

`getBy*` throws if missing, `queryBy*` returns null (use for "is not there"), `findBy*`
waits (async).
