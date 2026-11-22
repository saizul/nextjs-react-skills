---
name: server-actions-security
description: Secure Next.js Server Actions ("use server") and mutating Route Handlers - authentication and authorization inside every action, runtime input validation with zod (safeParse), CSRF and Origin checks (serverActions.allowedOrigins), open redirects, rate limiting for login/signup/contact actions, error leakage, closure and encryption key handling, and a data access layer with server-only. Includes a scanner that lists every Server Action and POST/PUT/PATCH/DELETE route handler and flags missing auth, missing validation, user-controlled redirects, missing rate limits, raw error returns, cookie-auth handlers without Origin checks, and unsafe next.config serverActions settings. Use when the user writes or reviews Server Actions, forms with useActionState, API routes in app/api, asks "is this server action secure", "do I need CSRF protection in Next.js", "how do I validate form data", or before shipping auth, payments, admin or user-data features.
license: MIT
compatibility: Next.js 14-16 App Router. Script needs Python 3.8+ only.
metadata:
  author: Saizul Amin
  version: "0.1.0"
---

# Server Actions security

A Server Action is a public POST endpoint. Anyone can call it with any arguments, whether or
not your UI shows the button. Every action therefore authenticates, validates, authorizes,
then mutates, in that order, inside the action itself.

Paths below are relative to this skill's folder (in Claude Code: `${CLAUDE_SKILL_DIR}`).

## When to use

- Writing or reviewing `'use server'` files, inline actions, `useActionState` forms
- Reviewing `app/**/route.ts` handlers that change data
- "Is this action secure?", "do I need CSRF tokens?", "how do I validate FormData?"
- Pre-release review of auth, billing, admin, file upload or user-data features

## When not to use

- General web app pentesting, dependency CVEs (`npm audit`), infrastructure hardening
- Authentication library setup from scratch (follow the library's docs; then come back to
  review the actions that use it)
- Environment variable exposure: use `nextjs-env-config`

## Workflow

1. **Find the auth helper.** Look for `auth()` (Auth.js), `currentUser()`/`auth()` (Clerk),
   `supabase.auth.getUser()`, `getServerSession`, or a project `verifySession()` in a DAL.
   Note its name; pass it to the scanner if it is custom.
2. **Run the scanner (read-only).**
   ```bash
   python3 scripts/action_scan.py .
   python3 scripts/action_scan.py . --auth-pattern 'requireMember\(' --validate-pattern 'checkInput\('
   python3 scripts/action_scan.py . --json --fail-on high
   ```
   Rules: SA001 no auth call, SA002 input without schema validation, SA003 redirect to user
   input, SA004 abuse-prone action without rate limit, SA005 raw error returned, SA006
   cookie-auth route handler without Origin/CSRF check, SA010 `allowedOrigins: ['*']`,
   SA011 huge `bodySizeLimit`. Functions marked `// action-scan: public` skip SA001 only.
3. **Review each action manually for authorization**, which no scanner can see:
   does the query scope by the current user (`where: { id, ownerId: session.user.id }`)?
   Can a member call an admin action? Are IDs from the client trusted? Check the threat list
   in [references/threat-model.md](references/threat-model.md).
4. **Rewrite unsafe actions** with the pattern in
   [references/secure-action-pattern.md](references/secure-action-pattern.md):
   auth -> `Schema.safeParse` -> authorization -> mutation -> `updateTag`/`revalidatePath`
   -> typed result. Move DB access into a `server-only` data access layer.
5. **Check route handlers.** Route handlers get no built-in CSRF protection. With cookie
   auth, verify `Origin` (or `Sec-Fetch-Site`) or require a token header; webhooks verify a
   signature instead of a session and are marked public.
6. **Check config.** `serverActions.allowedOrigins` only lists real front-end hosts behind a
   proxy; `bodySizeLimit` stays small; the proxy forwards `Host` and `X-Forwarded-Host`
   correctly (see `nextjs-deploy-selfhost`).
7. **Show diffs, wait for approval, then re-run the scanner.** Add tests that call the action
   directly without a session and with malformed input (see `react-testing`).

## Output

```
Server Actions review: 14 actions, 3 route handlers
High
- app/(admin)/actions.ts:22 deleteUser: no auth check; any visitor can delete any user
  fix: const session = await verifyAdmin(); then scope by id
- app/settings/actions.ts:8 updateEmail: FormData used without validation
Medium
- app/(auth)/actions.ts:5 login: no rate limit (credential stuffing)
- app/api/export/route.ts:3 POST uses cookies() but no Origin check
Authorization notes (manual)
- updateInvoice trusts invoiceId from the client; add where: { id, orgId: session.orgId }
Diffs: ...
```

## Rules

- Never rely on hiding a button, middleware/proxy alone, or TypeScript types for security.
- Return `{ ok: false, error: 'message' }` objects for expected failures; throw only for
  unexpected ones; never return `error.message` or stack traces.
- Do not pass secrets into inline actions through closures; read them inside the action.
- Rate limit by IP and by account for login, signup, password reset, OTP, contact forms.
