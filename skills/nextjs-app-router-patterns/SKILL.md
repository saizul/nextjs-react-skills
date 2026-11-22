---
name: nextjs-app-router-patterns
description: Design and review Next.js App Router code - layouts and route structure, Server vs Client Components and where to put the "use client" boundary, data fetching, caching and revalidation (Cache Components, "use cache", cacheLife, cacheTag, revalidateTag, updateTag, revalidatePath), streaming with Suspense and loading.tsx, parallel and intercepting routes, and Next.js 15/16 migration traps (async params, cookies(), headers(), proxy.ts, default.tsx). Includes a static checker for boundary mistakes. Use when the user builds or refactors pages, layouts or components in app/, asks "should this be a server or client component", "how do I fetch/cache/revalidate this data", hits errors like "useState only works in Client Components", "params should be awaited", "Event handlers cannot be passed to Client Component props", or upgrades to Next.js 16.
license: MIT
compatibility: Next.js 14-16 App Router (Next.js 16 defaults). Script needs Python 3.8+ only.
metadata:
  author: Saizul Amin
  version: "0.1.0"
---

# Next.js App Router patterns

Make the right structural decision first (route layout, server/client split, cache policy),
then write code. Server Components are the default; the client boundary goes as low in the
tree as possible.

Paths below are relative to this skill's folder (in Claude Code: `${CLAUDE_SKILL_DIR}`).

## When to use

- Creating or restructuring routes, layouts, route groups, `loading.tsx`, `error.tsx`
- "Server or client component?", "why is my whole page client-rendered?"
- Data fetching, caching and revalidation decisions; stale data after a mutation
- Errors: "You're importing a component that needs useState", "params is a Promise",
  "Event handlers cannot be passed to Client Component props", parallel route build errors
- Upgrading from Pages Router or from Next.js 14/15 to 16

## When not to use

- Server Action security review: use `server-actions-security`
- Metadata, sitemaps, OG images: use `nextjs-seo-metadata`
- Bundle size or re-render problems: use `react-performance-review`
- Pages Router-only projects (`pages/` with getServerSideProps): the advice differs

## Workflow

1. **Identify the version and config.** Read `package.json` (`next`, `react`) and
   `next.config.*`. Note `cacheComponents: true` (Next.js 16 opt-in caching model) and
   `output`. If `next` is below 15, `params`/`cookies()` are synchronous; say so.
2. **Run the boundary checker (read-only).**
   ```bash
   python3 scripts/rsc_boundary_check.py .            # project root
   python3 scripts/rsc_boundary_check.py . --json     # machine-readable
   python3 scripts/rsc_boundary_check.py . --strict   # also implicit client modules
   ```
   Exit 1 = findings at or above `--fail-on` (default `medium`). Rules: RSC001 hooks in a
   route file without "use client", RSC002 error.tsx not a client file, RSC003 "use client"
   on a layout/page, RSC004 metadata in a client file, RSC005 server-only import in a client
   file, RSC006 async client component, RSC008 sync params/cookies/headers, RSC009 initial
   fetch in useEffect, RSC011 one-argument revalidateTag, RSC012 slot without default.tsx,
   RSC013 middleware.ts.
3. **Decide each component's side** with the table in
   [references/decision-guide.md](references/decision-guide.md):
   - needs state, effects, event handlers, browser APIs, or a hook-only library -> client
   - fetches data, reads secrets, uses the filesystem/DB, or is mostly static markup -> server
   - both -> server parent fetches, passes serialisable props to a small client child;
     pass server-rendered UI into client wrappers via `children`
4. **Decide the data and cache policy** per data source (decision-guide.md, "Caching"):
   per-request (cookies/headers/user data) vs shared and cacheable; how stale it may be; what
   mutation must invalidate it (`updateTag` for read-your-writes in Server Actions,
   `revalidateTag(tag, 'max')` for background refresh, `revalidatePath` for whole routes).
5. **Write the code** using the recipes in [references/patterns.md](references/patterns.md):
   client islands, providers, Suspense streaming, parallel/intercepting routes, `server-only`.
   Fetch in parallel (`Promise.all`) instead of sequential awaits; wrap slow parts in
   `<Suspense>` so the shell streams first.
6. **Fix findings** in order: build breakers (RSC002, RSC004-RSC008, RSC012) first, then
   boundary placement (RSC001, RSC003), then deprecations (RSC011, RSC013). Show each diff.
   For upgrades, offer `npx @next/codemod@canary upgrade latest` and let the user run it.
7. **Verify.** Re-run the checker, then `npx next build` and read the route table
   (`○` static, `◐` partial prerender, `ƒ` dynamic). Explain any route that became dynamic
   unexpectedly (a `cookies()`/`headers()`/`searchParams` read or uncached fetch).

## Output

```
App Router review (Next.js 16.0, cacheComponents on)
Build breakers
- app/blog/[slug]/page.tsx:6  params.slug read synchronously -> const { slug } = await params
- app/dashboard/@analytics    missing default.tsx -> add default.tsx returning null
Boundary
- app/layout.tsx is 'use client' -> keep layout server-side, move <ThemeToggle> to components/
Caching plan
| data | where | policy | invalidated by |
| posts list | 'use cache' + cacheTag('posts') | cacheLife('hours') | updateTag('posts') in createPost |
| cart | per request (cookies) | not cached | - |
Diffs: ...
```

## Rules of thumb

- A `"use client"` file makes everything it imports client code too; Server Components passed
  as `children`/props stay on the server.
- Props crossing the boundary must be serialisable (no functions except Server Actions, no
  class instances, Dates become strings in some paths: pass ISO strings).
- Keep `layout.tsx` server-side; it renders once per navigation and does not re-render on
  child navigation, so do not read `searchParams` there.
- Put `import 'server-only'` at the top of modules that touch secrets or the database.
