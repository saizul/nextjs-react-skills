# Automated accessibility testing

Automated tools catch roughly 30-40% of WCAG issues. Use them to prevent regressions, not
as proof of accessibility.

## ESLint

```bash
npm i -D eslint-plugin-jsx-a11y
```

```js
// eslint.config.mjs (flat config)
import jsxA11y from 'eslint-plugin-jsx-a11y'

export default [
  // ...your existing config (eslint-config-next etc.)
  jsxA11y.flatConfigs.recommended,
]
```

Next.js 16 removed `next lint`; run `npx eslint .` in CI.

## Playwright + axe (rendered pages, recommended)

```bash
npm i -D @playwright/test @axe-core/playwright
```

```ts
// e2e/a11y.spec.ts
import { test, expect } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

const pages = ['/', '/pricing', '/login', '/checkout']

for (const path of pages) {
  test(`no a11y violations on ${path}`, async ({ page }) => {
    await page.goto(path)
    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'])
      .analyze()
    expect(results.violations).toEqual([])
  })
}

test('menu works with the keyboard', async ({ page }) => {
  await page.goto('/')
  await page.keyboard.press('Tab')
  await page.getByRole('button', { name: 'Menu' }).focus()
  await page.keyboard.press('Enter')
  await expect(page.getByRole('navigation')).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('button', { name: 'Menu' })).toBeFocused()
})
```

Run it against `next build && next start` (production output), not only `next dev`.

## Component tests (Vitest / Jest)

```bash
npm i -D vitest-axe        # or jest-axe for Jest
```

```ts
import { render } from '@testing-library/react'
import { axe } from 'vitest-axe'
import { expect, it } from 'vitest'
import { SignupForm } from './SignupForm'

it('has no detectable a11y violations', async () => {
  const { container } = render(<SignupForm />)
  expect(await axe(container)).toHaveNoViolations()
})
```

(Register the matcher in the setup file per the package README.) jsdom cannot compute color
contrast or layout, so these tests skip those rules; Playwright covers them.

## Testing Library queries as a11y checks

`getByRole('button', { name: 'Save' })` fails when the button has no accessible name or is a
div. Preferring role and label queries in all tests (see `react-testing`) turns every unit
test into a light accessibility test.

## Lighthouse CI

```bash
npx @lhci/cli autorun --collect.url=http://localhost:3000 --assert.preset=lighthouse:recommended
```

Use the accessibility category score as a floor (for example `>= 0.95`), not a target.

## Manual tools

- Browser: Chrome DevTools > Elements > Accessibility pane (computed name/role); Lighthouse
- Extensions: axe DevTools, WAVE, Accessibility Insights (FastPass, tab stops)
- Screen readers: VoiceOver (macOS/iOS), NVDA (Windows, free), TalkBack (Android)
