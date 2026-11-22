# Environment variable rules for Next.js

## Classify each variable

| Kind | Example | Prefix | Read where | When fixed |
| --- | --- | --- | --- | --- |
| Server secret | `DATABASE_URL`, `STRIPE_SECRET_KEY`, `AUTH_SECRET` | none | server only | runtime (dynamic) or build (static pages) |
| Server config | `LOG_LEVEL`, `FEATURE_X` | none | server only | same as above |
| Public, build-time | `NEXT_PUBLIC_SITE_URL`, `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` | `NEXT_PUBLIC_` | anywhere | `next build` (inlined) |
| Public, runtime | API base URL that differs per deployment of the same image | none | server, then passed as props | request time |

Publishable/anon keys designed for browsers (Stripe publishable, Supabase anon with RLS,
reCAPTCHA site key, Maps browser key restricted by referrer) are fine as `NEXT_PUBLIC_`.
Anything that grants write access or bypasses row-level security is a secret.

## How inlining works

At `next build`, every literal `process.env.NEXT_PUBLIC_X` is replaced with its value.
Not inlined (undefined in the browser):

```ts
process.env[name]                         // dynamic key
const { NEXT_PUBLIC_X } = process.env      // destructuring
const env = process.env; env.NEXT_PUBLIC_X // aliasing
```

Server-side code reads `process.env` normally. Values read during prerendering of a static
page are baked into that page's HTML at build time too; make the page dynamic (read
`cookies()`/`headers()` or `await connection()`) if the value must be read per request.

## Load order (first match wins)

1. `process.env` (real environment: shell, Docker, systemd, platform)
2. `.env.$(NODE_ENV).local`
3. `.env.local` (not loaded when `NODE_ENV=test`)
4. `.env.$(NODE_ENV)`
5. `.env`

- `.env`, `.env.development`, `.env.production`, `.env.test` may be committed for non-secret
  defaults; `*.local` files must not be.
- With a `src/` folder, `.env*` files stay in the project root.
- `$OTHER_VAR` expands inside `.env` files; escape a literal dollar as `\$`.
- `NODE_ENV` is set by Next.js (`development` for `next dev`, `production` otherwise); do
  not put it in `.env` files.

## Typed validation (fail fast)

```ts
// lib/env.ts
import 'server-only'
import { z } from 'zod'

const schema = z.object({
  DATABASE_URL: z.string().url(),
  STRIPE_SECRET_KEY: z.string().startsWith('sk_'),
  NEXT_PUBLIC_SITE_URL: z.string().url(),
})

export const env = schema.parse(process.env)
```

Client-safe values: a separate `lib/public-env.ts` that lists each
`process.env.NEXT_PUBLIC_X` literally (so they are inlined) and validates them. Libraries
such as `@t3-oss/env-nextjs` implement the same split.

## `server-only`

`import 'server-only'` at the top of a module makes the build fail if a Client Component
imports it, so a secret-reading module cannot be pulled into the browser bundle by accident.

## Outside Next.js (tests, ORM configs, scripts)

```ts
import { loadEnvConfig } from '@next/env'
loadEnvConfig(process.cwd())
```

Use it in a Jest/Vitest global setup or a Drizzle/Prisma config so they see the same values.
In tests `.env.local` is skipped; put test values in `.env.test`.

## One image, many environments (Docker)

`NEXT_PUBLIC_*` values are frozen in the image. Options:

1. **Build per environment** (simplest):
   ```dockerfile
   ARG NEXT_PUBLIC_SITE_URL
   ENV NEXT_PUBLIC_SITE_URL=$NEXT_PUBLIC_SITE_URL
   RUN npm run build
   ```
   `docker build --build-arg NEXT_PUBLIC_SITE_URL=https://staging.example.com .`
2. **Read at runtime on the server** and pass to the client:
   ```tsx
   // app/layout.tsx (server)
   import { connection } from 'next/server'
   export default async function RootLayout({ children }: { children: React.ReactNode }) {
     await connection()
     const config = { apiUrl: process.env.API_URL! } // not NEXT_PUBLIC_
     return <html lang="en"><body><ConfigProvider value={config}>{children}</ConfigProvider></body></html>
   }
   ```
   This makes the layout dynamic; acceptable for apps, costly for static marketing sites.

Never pass secrets as `--build-arg` unless the builder stage is discarded; build args are
visible in image history. Use BuildKit secrets (`RUN --mount=type=secret`) for build-time
secrets.

## Removed / legacy

- `serverRuntimeConfig` and `publicRuntimeConfig` were removed in Next.js 16; use env vars.
- `next.config` `env: { KEY: ... }` inlines values into client and server bundles like
  `NEXT_PUBLIC_`; prefer the prefix so intent is visible.

## Leak check after build

```bash
npx next build
grep -rl "sk_live_\|-----BEGIN" .next/static && echo "possible secret in client bundle"
```

Report only the file names found, not matching content.
