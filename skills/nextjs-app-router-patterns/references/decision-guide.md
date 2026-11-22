# Decision guide: server vs client, data fetching, caching

## Server or Client Component?

| Need | Server | Client |
| --- | --- | --- |
| Fetch data, query a DB, read secrets or files | yes | no |
| Large dependencies that should not ship to the browser (markdown, syntax highlight, date libs) | yes | no |
| `useState`, `useReducer`, `useEffect`, refs, context consumers | no | yes |
| `onClick`, `onChange`, other event handlers | no | yes |
| `window`, `localStorage`, `IntersectionObserver`, geolocation | no | yes |
| `useRouter`, `usePathname`, `useSearchParams` (next/navigation) | no | yes |
| `metadata` / `generateMetadata` export | yes (page/layout only) | ignored |
| `async` component | yes | no |

Default to server. When a component needs one interactive piece, extract that piece:

```
app/products/[id]/page.tsx        server: fetch product, render details
components/AddToCartButton.tsx    'use client': useState + onClick, gets productId prop
```

Context providers: create `app/providers.tsx` with `'use client'`, render it inside the root
layout around `{children}`. The layout stays a Server Component; pages below stay server.

## Fetching patterns

- Fetch where the data is used (in the Server Component), not at the top and drilled down.
  Duplicate `fetch` calls with the same URL/options are memoised per request; wrap non-fetch
  data access (ORM calls) in React `cache()` to dedupe within a request.
- Start independent requests together:
  ```ts
  const [user, posts] = await Promise.all([getUser(id), getPosts(id)])
  ```
- Slow, non-critical data goes behind `<Suspense fallback={...}>` so the page streams.
- Client-side fetching (SWR, TanStack Query) only for data that changes while the user is on
  the page (polling, infinite scroll, optimistic UI). Seed it with server data where possible.
- Never call your own Route Handler from a Server Component (`fetch('/api/x')`); call the
  function behind it directly.

## Caching (Next.js 16)

Two models exist. Check `next.config`:

### `cacheComponents: true` (opt-in in 16; explicit caching)

Everything is dynamic (rendered per request) unless you cache it:

```ts
import { cacheLife, cacheTag } from 'next/cache'

export async function getPosts() {
  'use cache'
  cacheLife('hours')   // built-in profiles: seconds, minutes, hours, days, weeks, max
  cacheTag('posts')
  return db.post.findMany()
}
```

- `'use cache'` at the top of a file, component or async function. Arguments and closed-over
  values become part of the cache key; they must be serialisable.
- Do not read `cookies()`/`headers()` inside a cached scope; read them outside and pass the
  needed value as an argument.
- Dynamic parts of a page must be inside `<Suspense>`; the rest is prerendered as a static shell
  (Partial Prerendering, `◐` in the build output).
- `'use cache: remote'` with `cacheHandlers` stores entries in shared storage (multi-instance).

### Without `cacheComponents` (Next.js 15 behaviour)

- `fetch` is not cached by default (since 15). Opt in per call:
  `fetch(url, { next: { revalidate: 3600, tags: ['posts'] } })` or `cache: 'force-cache'`.
- Route segment config still works: `export const revalidate = 3600`,
  `export const dynamic = 'force-static'`.
- `unstable_cache` wraps non-fetch data (superseded by `'use cache'`).

### Invalidation after a mutation

| API | Where | Behaviour | Use for |
| --- | --- | --- | --- |
| `updateTag('posts')` | Server Actions only | expires and re-reads in the same request | the user must see their own change immediately |
| `revalidateTag('posts', 'max')` | Actions, Route Handlers | stale-while-revalidate | content that can be eventually consistent (CMS webhooks) |
| `revalidatePath('/blog')` | Actions, Route Handlers | invalidates a route | when data is not tagged |
| `refresh()` | Server Actions only | re-renders uncached data, cache untouched | counters, notifications |
| `router.refresh()` | client | re-fetches the current route's RSC payload | after client-side mutations |

`revalidateTag(tag)` with one argument is deprecated in 16; always pass a profile.

### What makes a route dynamic

Reading `cookies()`, `headers()`, `draftMode()`, `searchParams`, `connection()`, or an
uncached data source during render. A page you expected to be static that shows `ƒ` in the
build output has one of these; move it into a Suspense-wrapped child or a client component.

## Route structure

- Route groups `(marketing)`, `(app)` share layouts without changing URLs; use them to give
  the logged-in area its own layout.
- `loading.tsx` = automatic Suspense boundary for the segment; `error.tsx` = client error
  boundary (must be `'use client'`); `not-found.tsx` with `notFound()`.
- Parallel routes `@slot` render side by side (dashboards); every slot needs `default.tsx`
  in Next.js 16.
- Intercepting routes `(.)photo/[id]` show a modal on client navigation and the full page on
  hard load.
- `proxy.ts` (formerly `middleware.ts`) runs before routing on the Node.js runtime; keep it
  to redirects, rewrites and cheap auth gates. Real authorisation belongs next to the data.

## Next.js 15 -> 16 checklist

- `params`, `searchParams`, `cookies()`, `headers()`, `draftMode()` must be awaited
- `middleware.ts` -> `proxy.ts`, export `proxy`
- `revalidateTag(tag)` -> `revalidateTag(tag, 'max')` or `updateTag(tag)`
- Parallel route slots need `default.tsx`
- `next lint` removed: run ESLint/Biome directly
- Turbopack is the default bundler (`--webpack` to opt out); Node.js 20.9+
- `experimental.dynamicIO` / `experimental.ppr` -> `cacheComponents`
- `next/image`: `priority` deprecated (use `preload` or `loading="eager"`), `images.domains`
  deprecated (use `remotePatterns`), default `qualities` is `[75]`
