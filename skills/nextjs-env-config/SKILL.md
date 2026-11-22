---
name: nextjs-env-config
description: Audit and fix environment variables in Next.js - which values reach the browser (NEXT_PUBLIC_ inlining at build time), secrets accidentally exposed through NEXT_PUBLIC_ names or next.config env, server-only variables read in Client Components (undefined at runtime), dynamic process.env access, .env file load order and .gitignore coverage, .env.example drift, runtime vs build-time values in Docker images, and typed env validation with zod. Includes an audit script that never prints values. Use when the user adds API keys or secrets to a Next.js app, asks "is it safe to use NEXT_PUBLIC_ for this", sees process.env.X undefined in the browser or after deploy, sets up .env files, builds one Docker image for several environments, or wants a secret-leak check before going public.
license: MIT
compatibility: Next.js 13-16. Script needs Python 3.8+ only; it reads files and prints variable names, never values.
metadata:
  author: Saizul Amin
  version: "0.1.0"
---

# Next.js environment configuration

Anything named `NEXT_PUBLIC_*`, and anything listed in `next.config` `env`, is copied into
the JavaScript every visitor downloads. Everything else exists only on the server. Most env
bugs and leaks come from mixing up those two worlds.

Paths below are relative to this skill's folder (in Claude Code: `${CLAUDE_SKILL_DIR}`).

## When to use

- Adding Stripe/OpenAI/database credentials, "where do I put my API key?"
- "process.env.X is undefined" in the browser, in tests, or only in production/Docker
- Before making a repository public or after a suspected secret leak
- Setting up `.env*` files, `.env.example`, CI or Docker build arguments

## When not to use

- Secret storage and rotation on a platform (Vercel, Doppler, Vault): follow its docs
- Secrets already committed to git history: rotate them first, then clean history
  (`git filter-repo`); this skill only finds current exposure
- Feature-flag systems

## Workflow

1. **Run the audit (read-only, no values printed).**
   ```bash
   python3 scripts/env_audit.py .
   python3 scripts/env_audit.py . --json
   ```
   Rules: ENV001 env file not gitignored, ENV002 secret-looking value in NEXT_PUBLIC_,
   ENV003 secret-looking NEXT_PUBLIC_ name, ENV004 NODE_ENV in a file, ENV005 dynamic or
   destructured process.env in client code, ENV006 server variable in a Client Component,
   ENV007/ENV008 .env.example drift, ENV009 no .env.example, ENV010 next.config `env`,
   ENV011 NEXT_PUBLIC_ variable missing from the Dockerfile build.
2. **Treat any exposed secret as compromised.** If ENV002/ENV003/ENV010 (high) hit a real
   credential that has been deployed or committed, tell the user to rotate it at the provider
   now; renaming the variable does not un-leak it. Do not print or paste the value.
3. **Classify every variable** with [references/env-rules.md](references/env-rules.md):
   server secret, server config, public build-time value, or public runtime value.
4. **Fix the code:**
   - secrets: drop `NEXT_PUBLIC_`, read them only in Server Components, Server Actions,
     Route Handlers or a `server-only` module; pass derived results to the client
   - client code: write `process.env.NEXT_PUBLIC_X` literally (no `process.env[name]`, no
     destructuring)
   - `next.config` `env`: remove; it is the old way to inline values
   - add a typed env module (`lib/env.ts`, zod) that fails fast at startup
5. **Fix the files:** `.gitignore` gets `.env*` and `!.env.example`; `.env.example` lists every
   name with empty or dummy values; `.env.local` holds local secrets.
6. **Fix build vs runtime.** `NEXT_PUBLIC_*` is frozen at `next build`. For one Docker image
   across staging/production, either build per environment with `--build-arg`, or read the
   value on the server at request time and pass it down (see env-rules.md, "One image, many
   environments").
7. **Verify.** Re-run the audit; build and search the client output for a known secret
   name (`grep -r "STRIPE_SECRET" .next/static` should find nothing); check the feature in
   the browser.

## Output

```
Env audit: 2 high, 1 medium, 3 low
High
- .env.local: NEXT_PUBLIC_OPENAI_API_KEY - secret name with public prefix -> rotate key,
  rename to OPENAI_API_KEY, call OpenAI from a Server Action
- components/Checkout.tsx:4 reads DATABASE_URL in a Client Component (undefined; never do this)
Medium
- Dockerfile builds without ARG NEXT_PUBLIC_API_URL -> value is empty in the image
Low
- 3 variables missing from .env.example (names listed)
Changes: lib/env.ts (zod schema), app/actions/ai.ts (server call), .gitignore, .env.example
```

## Never

- Print, log, echo or paste env values (including in `--json` output, test snapshots,
  error messages or this conversation)
- Commit `.env.local` or any file with real secrets
- Use `NEXT_PUBLIC_` to "fix" an undefined variable without asking whether it is secret
