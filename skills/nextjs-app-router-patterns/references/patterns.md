# App Router code patterns

## Client island inside a server page

```tsx
// app/products/[id]/page.tsx (Server Component)
import { notFound } from 'next/navigation'
import { getProduct } from '@/lib/products'
import { AddToCart } from '@/components/AddToCart'

export default async function ProductPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  const product = await getProduct(id)
  if (!product) notFound()
  return (
    <main>
      <h1>{product.name}</h1>
      <p>{product.description}</p>
      <AddToCart productId={product.id} price={product.price} />
    </main>
  )
}
```

```tsx
// components/AddToCart.tsx
'use client'
import { useTransition } from 'react'
import { addToCart } from '@/app/actions'

export function AddToCart({ productId, price }: { productId: string; price: number }) {
  const [pending, start] = useTransition()
  return (
    <button type="button" disabled={pending} onClick={() => start(() => addToCart(productId))}>
      {pending ? 'Adding...' : `Add to cart (${price})`}
    </button>
  )
}
```

## Server content inside a client wrapper

```tsx
// components/Tabs.tsx
'use client'
import { useState, type ReactNode } from 'react'

export function Tabs({ tabs }: { tabs: { label: string; content: ReactNode }[] }) {
  const [i, setI] = useState(0)
  return (
    <div>
      <div role="tablist">
        {tabs.map((t, n) => (
          <button key={t.label} role="tab" aria-selected={n === i} onClick={() => setI(n)}>
            {t.label}
          </button>
        ))}
      </div>
      <div role="tabpanel">{tabs[i].content}</div>
    </div>
  )
}

// page.tsx (server): <Tabs tabs={[{ label: 'Specs', content: <Specs id={id} /> }]} />
// <Specs> is an async Server Component; it renders on the server and is passed as a prop.
```

## Providers

```tsx
// app/providers.tsx
'use client'
import { ThemeProvider } from 'next-themes'
export function Providers({ children }: { children: React.ReactNode }) {
  return <ThemeProvider attribute="class">{children}</ThemeProvider>
}

// app/layout.tsx (server)
import { Providers } from './providers'
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body><Providers>{children}</Providers></body>
    </html>
  )
}
```

## Streaming with Suspense

```tsx
import { Suspense } from 'react'

export default function Dashboard() {
  return (
    <>
      <Header />                       {/* fast, static */}
      <Suspense fallback={<StatsSkeleton />}>
        <Stats />                      {/* async, slow query */}
      </Suspense>
      <Suspense fallback={<FeedSkeleton />}>
        <Feed />
      </Suspense>
    </>
  )
}
```

Behind nginx, streaming needs `proxy_buffering off` (see `nextjs-deploy-selfhost`).

## Data access layer with server-only

```ts
// lib/dal.ts
import 'server-only'
import { cache } from 'react'
import { cookies } from 'next/headers'

export const getCurrentUser = cache(async () => {
  const token = (await cookies()).get('session')?.value
  if (!token) return null
  return verifyAndLoadUser(token)
})
```

Importing `lib/dal.ts` from a client file now fails the build instead of leaking code.

## Cached data function (cacheComponents)

```ts
import { cacheLife, cacheTag } from 'next/cache'

export async function getCategory(slug: string) {
  'use cache'
  cacheLife('days')
  cacheTag(`category-${slug}`)
  return db.category.findUnique({ where: { slug } })
}
```

## Mutation with immediate refresh

```ts
'use server'
import { updateTag } from 'next/cache'

export async function renameCategory(slug: string, name: string) {
  // auth + validation first: see server-actions-security
  await db.category.update({ where: { slug }, data: { name } })
  updateTag(`category-${slug}`)
}
```

## generateStaticParams for known dynamic routes

```ts
export async function generateStaticParams() {
  const posts = await getAllSlugs()
  return posts.map((slug) => ({ slug }))
}
export const dynamicParams = true // unknown slugs render on demand (false -> 404)
```

## Parallel route slot default

```tsx
// app/dashboard/@analytics/default.tsx
export default function Default() {
  return null
}
```

## Error boundary

```tsx
// app/dashboard/error.tsx
'use client'
export default function Error({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div role="alert">
      <p>Could not load the dashboard.</p>
      <button type="button" onClick={() => reset()}>Try again</button>
    </div>
  )
}
```

## Common error messages

| Message | Cause | Fix |
| --- | --- | --- |
| "You're importing a component that needs useState..." | hook in a file without 'use client' | add the directive to the smallest component that needs it |
| "Event handlers cannot be passed to Client Component props" | passing `onClick` from a server file | move the handler into the client component |
| "Functions cannot be passed directly to Client Components" | non-action function prop | pass data, or a Server Action |
| "Route used `params.x`. `params` should be awaited" | sync params (15+) | `const { x } = await params` |
| "async/await is not yet supported in Client Components" | async client component | fetch in a server parent |
| Hydration mismatch | `Date.now()`, `Math.random()`, `window` checks in render | compute in `useEffect`, or render on the server only |
