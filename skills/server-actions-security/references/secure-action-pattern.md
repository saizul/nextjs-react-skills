# Secure Server Action pattern

## Data access layer

```ts
// lib/dal.ts
import 'server-only'
import { cache } from 'react'
import { redirect } from 'next/navigation'
import { auth } from '@/auth' // Auth.js; adapt for Clerk, Supabase, Better Auth, Lucia...

export const verifySession = cache(async () => {
  const session = await auth()
  if (!session?.user?.id) redirect('/login')
  return { userId: session.user.id, role: session.user.role as 'member' | 'admin' }
})

export async function requireAdmin() {
  const s = await verifySession()
  if (s.role !== 'admin') throw new Error('Forbidden')
  return s
}
```

## The action

```ts
// app/invoices/actions.ts
'use server'
import { z } from 'zod'
import { updateTag } from 'next/cache'
import { verifySession } from '@/lib/dal'
import { db } from '@/lib/db'

const UpdateInvoice = z.object({
  id: z.string().uuid(),
  amount: z.coerce.number().positive().max(1_000_000),
  note: z.string().trim().max(500).optional(),
})

export type ActionResult = { ok: true } | { ok: false; error: string; fieldErrors?: Record<string, string[]> }

export async function updateInvoice(_prev: ActionResult | null, formData: FormData): Promise<ActionResult> {
  // 1. authenticate
  const { userId } = await verifySession()

  // 2. validate (never trust types: the client can send anything)
  const parsed = UpdateInvoice.safeParse(Object.fromEntries(formData))
  if (!parsed.success) {
    return { ok: false, error: 'Invalid input', fieldErrors: z.flattenError(parsed.error).fieldErrors }
  }
  const { id, amount, note } = parsed.data

  // 3. authorize: scope the write to records this user owns
  const result = await db.invoice.updateMany({
    where: { id, ownerId: userId, status: 'draft' },
    data: { amount, note },
  })
  if (result.count === 0) return { ok: false, error: 'Invoice not found' }

  // 4. refresh caches the user will look at next
  updateTag(`invoice-${id}`)
  return { ok: true }
}
```

Notes:
- `z.flattenError` is zod 4; with zod 3 use `parsed.error.flatten().fieldErrors`.
- `updateMany` with an ownership filter avoids a separate "load then check" race.
- Bound arguments (`updateInvoice.bind(null, id)`) are visible to and modifiable by the
  client like any other argument; validate them too.

## Client form

```tsx
'use client'
import { useActionState } from 'react'
import { updateInvoice } from './actions'

export function InvoiceForm({ id }: { id: string }) {
  const [state, action, pending] = useActionState(updateInvoice, null)
  return (
    <form action={action}>
      <input type="hidden" name="id" value={id} />
      <label htmlFor="amount">Amount</label>
      <input id="amount" name="amount" inputMode="decimal" aria-describedby="amount-error" />
      {state && !state.ok && <p id="amount-error" role="alert">{state.fieldErrors?.amount?.[0] ?? state.error}</p>}
      <button disabled={pending}>Save</button>
    </form>
  )
}
```

## Safe redirect after login

```ts
function safeNext(value: unknown): string {
  const s = typeof value === 'string' ? value : '/'
  return s.startsWith('/') && !s.startsWith('//') && !s.startsWith('/\\') ? s : '/'
}
redirect(safeNext(formData.get('next')))
```

## Rate limiting

```ts
// lib/ratelimit.ts (Upstash example; any shared store works)
import 'server-only'
import { Ratelimit } from '@upstash/ratelimit'
import { Redis } from '@upstash/redis'
export const loginLimit = new Ratelimit({ redis: Redis.fromEnv(), limiter: Ratelimit.slidingWindow(5, '10 m') })

// in the action
import { headers } from 'next/headers'
const ip = (await headers()).get('x-forwarded-for')?.split(',')[0]?.trim() ?? 'unknown'
const { success } = await loginLimit.limit(`login:${ip}:${email}`)
if (!success) return { ok: false, error: 'Too many attempts, try again later' }
```

Only trust `X-Forwarded-For` when your proxy sets it (and strips client-supplied values).
An in-memory `Map` limiter works only with a single instance.

## Route handler with cookie auth

```ts
// app/api/export/route.ts
import { verifySession } from '@/lib/dal'

export async function POST(request: Request) {
  const origin = request.headers.get('origin')
  const host = request.headers.get('x-forwarded-host') ?? request.headers.get('host')
  if (!origin || new URL(origin).host !== host) return new Response('Forbidden', { status: 403 })
  const { userId } = await verifySession()
  const body = ExportSchema.parse(await request.json())
  // ...
}
```

Also set cookies with `SameSite=Lax` (or `Strict`), `HttpOnly`, `Secure`.

## Webhooks (public, signature-verified)

```ts
// action-scan: public (verified by signature)
export async function POST(request: Request) {
  const raw = await request.text()
  const sig = request.headers.get('stripe-signature')
  const event = stripe.webhooks.constructEvent(raw, sig!, process.env.STRIPE_WEBHOOK_SECRET!)
  // handle idempotently (store event.id)
}
```

## next.config

```ts
const nextConfig = {
  experimental: {
    serverActions: {
      allowedOrigins: ['app.example.com'], // only when a proxy changes the Host/Origin
      bodySizeLimit: '2mb',                 // default 1mb; upload big files to storage directly
    },
  },
}
```

## Next-safe-action / similar wrappers

Libraries like `next-safe-action` centralise auth (`authActionClient.use(...)`) and schema
validation (`.inputSchema(zodSchema)`). The scanner treats `authActionClient` and
`.inputSchema(` / `.schema(` as auth/validation; pass other wrapper names with
`--auth-pattern` and `--validate-pattern`.
