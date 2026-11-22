# Test setup for Next.js

## Vitest (recommended for new projects)

Install (TypeScript project, per the Next.js Vitest guide, plus user-event and jest-dom):

```bash
npm install -D vitest @vitejs/plugin-react jsdom @testing-library/react @testing-library/dom vite-tsconfig-paths \
  @testing-library/user-event @testing-library/jest-dom
```

```ts
// vitest.config.mts
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tsconfigPaths from 'vite-tsconfig-paths'

export default defineConfig({
  plugins: [tsconfigPaths(), react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./vitest.setup.ts'],
    restoreMocks: true,
  },
})
```

```ts
// vitest.setup.ts
import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

afterEach(() => cleanup())
```

```json
// package.json
{ "scripts": { "test": "vitest", "test:run": "vitest run" } }
```

TypeScript types for jest-dom matchers: the `/vitest` import above extends `expect`; add
`"types": ["vitest/globals"]` only if you enable `globals: true`.

## Jest (existing projects)

```bash
npm install -D jest jest-environment-jsdom @testing-library/react @testing-library/dom \
  @testing-library/user-event @testing-library/jest-dom @types/jest ts-node
```

```ts
// jest.config.ts
import type { Config } from 'jest'
import nextJest from 'next/jest.js'

const createJestConfig = nextJest({ dir: './' }) // loads next.config and .env files

const config: Config = {
  testEnvironment: 'jsdom',
  setupFilesAfterEnv: ['<rootDir>/jest.setup.ts'],
  moduleNameMapper: { '^@/(.*)$': '<rootDir>/src/$1' }, // match tsconfig paths
}

export default createJestConfig(config)
```

```ts
// jest.setup.ts
import '@testing-library/jest-dom'
```

`next/jest` sets up SWC transforms, CSS/image mocks and env loading.

## Playwright (E2E, async Server Components)

```bash
npm init playwright@latest
```

```ts
// playwright.config.ts (excerpt)
webServer: { command: 'npm run build && npm run start', url: 'http://localhost:3000', reuseExistingServer: !process.env.CI },
use: { baseURL: 'http://localhost:3000' },
```

## Environment variables in tests

`NODE_ENV=test` skips `.env.local`. Put test values in `.env.test`, and load them the way
Next.js does in a global setup:

```ts
import { loadEnvConfig } from '@next/env'
export default async () => loadEnvConfig(process.cwd())
```

## CI

```yaml
- run: npm ci
- run: npx vitest run --coverage    # or npx jest --ci
- run: npx playwright install --with-deps && npx playwright test
```

Fail CI on focused tests: Vitest `--allowOnly=false` (default in CI when `process.env.CI` is
set), Jest via the `jest/no-focused-tests` ESLint rule, or
`python3 scripts/find_test_gaps.py .` (exit 1 on `.only`).

## Common setup errors

| Error | Fix |
| --- | --- |
| `document is not defined` | set `environment: 'jsdom'` (or `// @vitest-environment jsdom` per file) |
| `toBeInTheDocument is not a function` | import jest-dom in the setup file |
| Cannot resolve `@/components/...` | `vite-tsconfig-paths` (Vitest) or `moduleNameMapper` (Jest) |
| `invariant expected app router to be mounted` | mock `next/navigation` (see recipes) |
| `Objects are not valid as a React child (found: [object Promise])` | async Server Component rendered in a unit test: use Playwright, or test its data function |
| CSS module / image import errors in Jest | use `next/jest`, which mocks them |
