---
name: nextjs-deploy-selfhost
description: Self-host a Next.js app on a VPS or in containers - output standalone builds, multi-stage Dockerfile (Node.js 20.9+, non-root, HOSTNAME=0.0.0.0, node server.js, .next/static and public copied), .dockerignore, nginx reverse proxy (Host and X-Forwarded headers, streaming without buffering, /_next/static caching, safe proxy_cache), systemd or PM2 without Docker, static export limits, image optimization with sharp, Cache-Control behaviour, and multi-instance needs (shared cacheHandler, deploymentId, NEXT_SERVER_ACTIONS_ENCRYPTION_KEY, graceful shutdown). Includes a checker for next.config, Dockerfile, .dockerignore and nginx configs. Use when the user deploys Next.js without Vercel, writes a Dockerfile or nginx config for Next.js, sees missing CSS/JS (404 on /_next/static) after a Docker deploy, "Failed to find Server Action" errors, streaming that does not stream, huge images, or scales to more than one instance.
license: MIT
compatibility: Next.js 14-16, Docker, nginx 1.18+. Script needs Python 3.8+ only and reads files; it never builds, connects or deploys.
metadata:
  author: Saizul Amin
  version: "0.1.0"
---

# Self-hosting Next.js

`output: 'standalone'` + a small multi-stage Docker image + nginx in front is the default
recipe. It gives every Next.js feature (Server Actions, ISR, image optimization, streaming)
without a platform. Static export is only for sites with no server features.

Paths below are relative to this skill's folder (in Claude Code: `${CLAUDE_SKILL_DIR}`).

## When to use

- "Deploy Next.js to my VPS / Docker / Kubernetes / Coolify / Dokploy"
- Writing or reviewing a Dockerfile, compose file or nginx config for Next.js
- Errors after deploy: CSS/JS 404, `Failed to find Server Action`, `Invalid Server Actions
  request`, images slow or memory spikes, Suspense content arriving all at once
- Scaling to several instances behind a load balancer

## When not to use

- Vercel, Netlify, Cloudflare or AWS Amplify deployments (platform adapters handle this)
- Generic server hardening, TLS certificates, firewall (use a server/DevOps skill)
- Environment variable exposure questions: use `nextjs-env-config`

## Workflow

1. **Pick the mode** with the user:
   - Node server (`output: 'standalone'`), in Docker or under systemd/PM2: full features
   - Static export (`output: 'export'`) served by nginx/CDN: no Server Actions, route
     handlers with POST, proxy.ts, cookies/headers, ISR, or default image optimization
   Ask how many instances will run and whether a CDN sits in front.
2. **Run the checker (read-only).**
   ```bash
   python3 scripts/selfhost_check.py .
   python3 scripts/selfhost_check.py . --nginx /etc/nginx/sites-available/app.conf --instances 2
   python3 scripts/selfhost_check.py . --json
   ```
   Rules: DEP001 Dockerfile without standalone, DEP002/003 image config, DEP005-007
   multi-instance (cache handler, deploymentId, encryption key), DEP010/011 static export
   conflicts, DEP020-030 Dockerfile and .dockerignore, DEP040-046 nginx.
3. **Write or fix the files** from [references/docker-nginx.md](references/docker-nginx.md):
   `next.config` (`output: 'standalone'`), Dockerfile, `.dockerignore`, compose service with a
   healthcheck, nginx server block, or a systemd unit for a non-Docker VPS.
4. **Plan caching and scaling** with [references/caching-and-scaling.md](references/caching-and-scaling.md):
   which responses nginx/CDN may cache (only `/_next/static`, `/_next/image`, public assets
   and pages that send `public` Cache-Control), shared cache handler for >1 instance,
   `deploymentId` for rolling deploys, persistent `.next/cache` for ISR and images.
5. **Show every file diff and the exact deploy commands; wait for confirmation** before
   anything that touches a server (copying files, `docker compose up -d`, `nginx -t && systemctl
   reload nginx`). Never restart production services without a yes.
6. **Verify after deploy:**
   ```bash
   curl -sI https://example.com/ | grep -i -E 'cache-control|x-powered-by'
   curl -sI https://example.com/_next/static/chunks/<any>.js | grep -i cache-control  # immutable
   docker compose ps          # healthy
   docker compose logs --tail 50 web
   ```
   Submit a form that uses a Server Action and load a page with a Suspense boundary to
   confirm streaming (content should appear progressively).

## Output

```
Self-host review (Docker + nginx, 2 instances)
High
- Dockerfile copies .next/standalone but not .next/static -> all JS/CSS 404
- nginx: proxy_cache with proxy_ignore_headers Cache-Control -> logged-in pages cached for everyone
Medium
- 2 instances, no shared cacheHandler: ISR pages differ per instance
- no NEXT_SERVER_ACTIONS_ENCRYPTION_KEY: "Failed to find Server Action" across instances
Files: next.config.ts, Dockerfile, .dockerignore, compose.yaml, nginx/app.conf (diffs below)
Deploy: docker compose build && docker compose up -d   (waiting for your go-ahead)
```

## Key facts

- The standalone folder does not include `public/` or `.next/static/`; copy both.
- `server.js` listens on `HOSTNAME`/`PORT`; set `HOSTNAME=0.0.0.0` in containers.
- Next.js 16 needs Node.js 20.9+.
- Dynamic pages send `Cache-Control: private, no-cache, no-store, max-age=0, must-revalidate`;
  never override it at the proxy.
