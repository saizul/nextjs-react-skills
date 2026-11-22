# Testing recipes (Testing Library + Vitest; Jest: replace `vi` with `jest`)

## Component with interaction

```tsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { Counter } from './Counter'

describe('Counter', () => {
  it('increments when the button is clicked', async () => {
    const user = userEvent.setup()
    render(<Counter initial={1} />)
    await user.click(screen.getByRole('button', { name: /increment/i }))
    expect(screen.getByText('Count: 2')).toBeInTheDocument()
  })
})
```

## Form with validation and submit

```tsx
it('shows an error for an invalid email and does not submit', async () => {
  const user = userEvent.setup()
  const onSubmit = vi.fn()
  render(<SignupForm onSubmit={onSubmit} />)

  await user.type(screen.getByLabelText(/email/i), 'not-an-email')
  await user.click(screen.getByRole('button', { name: /sign up/i }))

  expect(await screen.findByRole('alert')).toHaveTextContent(/valid email/i)
  expect(onSubmit).not.toHaveBeenCalled()
})
```

## Mock next/navigation

```ts
import { vi } from 'vitest'

const push = vi.fn()
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push, replace: vi.fn(), refresh: vi.fn(), back: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => '/products',
  useSearchParams: () => new URLSearchParams('q=shoes'),
  useParams: () => ({ id: '42' }),
  redirect: vi.fn(),
  notFound: vi.fn(),
}))

// in a test
await user.click(screen.getByRole('button', { name: /next page/i }))
expect(push).toHaveBeenCalledWith('/products?page=2')
```

## Mock a Server Action module used by a Client Component

```ts
vi.mock('@/app/actions', () => ({
  addToCart: vi.fn().mockResolvedValue({ ok: true }),
}))
import { addToCart } from '@/app/actions'

it('calls the action with the product id', async () => {
  const user = userEvent.setup()
  render(<AddToCart productId="p1" price={10} />)
  await user.click(screen.getByRole('button', { name: /add to cart/i }))
  expect(addToCart).toHaveBeenCalledWith('p1')
})
```

## Test a Server Action itself (plain async function)

```ts
vi.mock('@/lib/dal', () => ({ verifySession: vi.fn() }))
vi.mock('@/lib/db', () => ({ db: { invoice: { updateMany: vi.fn().mockResolvedValue({ count: 1 }) } } }))
vi.mock('next/cache', () => ({ updateTag: vi.fn(), revalidatePath: vi.fn() }))

import { verifySession } from '@/lib/dal'
import { updateInvoice } from './actions'

it('rejects invalid input', async () => {
  vi.mocked(verifySession).mockResolvedValue({ userId: 'u1', role: 'member' })
  const fd = new FormData()
  fd.set('id', 'not-a-uuid')
  expect(await updateInvoice(null, fd)).toMatchObject({ ok: false })
})

it('requires a session', async () => {
  vi.mocked(verifySession).mockRejectedValue(new Error('NEXT_REDIRECT'))
  await expect(updateInvoice(null, new FormData())).rejects.toThrow()
})
```

Server Action tests run in the `node` environment: add `// @vitest-environment node` at the
top of the file.

## Network with MSW

```ts
// test/server.ts
import { setupServer } from 'msw/node'
import { http, HttpResponse } from 'msw'

export const server = setupServer(
  http.get('https://api.example.com/products', () => HttpResponse.json([{ id: 1, name: 'Shoe' }])),
)

// vitest.setup.ts
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

// in a test: override for one case
server.use(http.get('https://api.example.com/products', () => new HttpResponse(null, { status: 500 })))
expect(await screen.findByText(/could not load products/i)).toBeInTheDocument()
```

## Hooks

```ts
import { act, renderHook } from '@testing-library/react'

it('adds and removes items', () => {
  const { result } = renderHook(() => useCart())
  act(() => result.current.add('a'))
  act(() => result.current.remove('a'))
  expect(result.current.items).toEqual([])
})

// hook needing a provider
const wrapper = ({ children }: { children: React.ReactNode }) => <CartProvider>{children}</CartProvider>
renderHook(() => useCart(), { wrapper })
```

## Custom render with providers

```tsx
// test/render.tsx
import { render, type RenderOptions } from '@testing-library/react'
export function renderWithProviders(ui: React.ReactElement, options?: RenderOptions) {
  return render(ui, { wrapper: ({ children }) => <ThemeProvider><QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider></ThemeProvider>, ...options })
}
```

## Timers (debounce, polling)

```ts
it('searches after the debounce', async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
  render(<Search onSearch={onSearch} />)
  await user.type(screen.getByRole('searchbox'), 'shoe')
  vi.advanceTimersByTime(300)
  expect(onSearch).toHaveBeenCalledWith('shoe')
  vi.useRealTimers()
})
```

## Synchronous Server Components

Synchronous Server Components render like any component. For async ones, test the data
function separately and cover the page with Playwright:

```ts
// e2e/product.spec.ts
test('product page shows price', async ({ page }) => {
  await page.goto('/products/42')
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Running shoe')
  await expect(page.getByText('$89')).toBeVisible()
})
```

## Fixing common failures

| Symptom | Cause | Fix |
| --- | --- | --- |
| "Unable to find role button with name X" | name comes from aria-label / text differs | check the DOM dump; fix the label in the component |
| "not wrapped in act(...)" | state update after the test finished | `await` the user-event call; use `findBy*` for the final state |
| Test passes alone, fails in suite | shared module state, un-reset mocks | `restoreMocks: true`, reset stores in `beforeEach` |
| Flaky timing | real timers / sleeps | fake timers or `findBy*` |
| `window.matchMedia is not a function` | jsdom lacks it | stub in setup: `window.matchMedia = vi.fn().mockReturnValue({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() })` |
| `IntersectionObserver is not defined` | jsdom lacks it | stub a minimal class in setup |
