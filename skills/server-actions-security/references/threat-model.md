# Threat model for Server Actions and Route Handlers

| Threat | How it happens | Built-in protection | What you must do |
| --- | --- | --- | --- |
| Unauthenticated call | Action IDs are in the client bundle; anyone can POST to them | none | authenticate in every action |
| Broken object-level authorization (IDOR) | client sends another user's record id | none | scope every query by the session's user/org |
| Privilege escalation | member calls an admin action | none | role check in the action, not just in the UI |
| Mass assignment | `data: Object.fromEntries(formData)` writes `role`, `ownerId` | none | parse with an explicit schema; pick fields |
| Injection | raw SQL with string interpolation, `$queryRawUnsafe` | ORM parameterisation | tagged templates / parameters only |
| CSRF on actions | cross-site form post | Origin compared with `x-forwarded-host`/`host`, POST-only, SameSite cookies; requests without an `Origin` header skip the comparison | keep `allowedOrigins` tight (never `'*'` or `'**'`); SameSite=Lax cookies |
| CSRF on route handlers | cross-site POST with cookies | none | Origin check or token header; SameSite cookies |
| Open redirect | `redirect(formData.get('next'))` | none | allow relative paths only |
| Credential stuffing / spam | scripted calls to login, signup, contact | none | rate limit by IP + account; captcha after N failures |
| Information leak | returning `error.message`, stack, DB errors | prod builds hide thrown error messages from the client (digest only) | return generic messages; log details server-side |
| Secret leak via closure | inline action captures a secret variable | closures are encrypted | still avoid: read secrets inside the action |
| Version skew / key mismatch | multiple instances with different keys | per-build key | set `NEXT_SERVER_ACTIONS_ENCRYPTION_KEY` for multi-instance |
| Large payload DoS | huge FormData / JSON | `bodySizeLimit` (1 MB default) | keep it small; stream uploads to object storage |
| Replay / double submit | user clicks twice, attacker replays | none | idempotency keys for payments; unique constraints |
| SSRF | action fetches a user-supplied URL | none | allowlist hosts; block private IP ranges |
| Path traversal | action reads `fs` path from input | none | resolve and verify the path stays in a base dir |

## Questions to ask for each action

1. Who may call this? (anonymous, any user, owner, admin)
2. What records can it touch, and is the query scoped to them?
3. Which fields are written, and are they listed explicitly in the schema?
4. What happens if it runs twice, concurrently, or with a 10 MB string?
5. Where does it redirect, and can the destination be influenced?
6. What does the client see on failure?

## Middleware / proxy is not enough

`proxy.ts` (formerly `middleware.ts`) can redirect unauthenticated visitors, but Server
Actions and route handlers must still check the session: matchers are easy to get wrong,
and past framework bugs have allowed proxy bypass. Treat the proxy as UX, the action as the
security boundary.
