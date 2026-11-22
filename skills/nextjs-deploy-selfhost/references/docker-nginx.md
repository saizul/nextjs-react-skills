# Docker, nginx and systemd files for Next.js

## next.config.ts

```ts
import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  output: 'standalone',
  poweredByHeader: false,
  // multi-instance only (see caching-and-scaling.md):
  // deploymentId: process.env.DEPLOYMENT_VERSION,
  // cacheHandler: require.resolve('./cache-handler.js'),
  // cacheMaxMemorySize: 0,
}

export default nextConfig
```

Monorepo: set `outputFileTracingRoot: path.join(__dirname, '../../')` so dependencies outside
the app folder are traced.

## Dockerfile (npm; adapt the install step for pnpm/yarn/bun)

```dockerfile
# syntax=docker/dockerfile:1
FROM node:22-alpine AS base
RUN apk add --no-cache libc6-compat

FROM base AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
# Public values are inlined now; pass them as build args (never secrets)
ARG NEXT_PUBLIC_SITE_URL
ENV NEXT_PUBLIC_SITE_URL=$NEXT_PUBLIC_SITE_URL
# Same key for every instance of this build (multi-instance only)
RUN --mount=type=secret,id=actions_key \
    if [ -f /run/secrets/actions_key ]; then \
      export NEXT_SERVER_ACTIONS_ENCRYPTION_KEY="$(cat /run/secrets/actions_key)"; \
    fi; \
    npm run build

FROM base AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV HOSTNAME="0.0.0.0"
ENV PORT=3000
RUN addgroup -S -g 1001 nodejs && adduser -S -u 1001 -G nodejs nextjs
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
RUN mkdir -p .next/cache && chown nextjs:nodejs .next/cache
USER nextjs
EXPOSE 3000
CMD ["node", "server.js"]
```

- Typical image size: 150-250 MB (vs 1 GB+ for a single-stage image with dev dependencies).
- `sharp` is included automatically in standalone output when installed (Next.js 15+ lists it
  as an optional dependency); on Alpine `libc6-compat` helps native modules.
- If the build needs no secret, drop the `--mount=type=secret` line and use plain `RUN npm run build`.

## .dockerignore

```
node_modules
.next
.git
.github
.env*
!.env.example
npm-debug.log*
coverage
playwright-report
Dockerfile*
compose*.yaml
```

## compose.yaml

```yaml
services:
  web:
    build:
      context: .
      args:
        NEXT_PUBLIC_SITE_URL: https://example.com
      secrets: [actions_key]
    image: acme-web:${GIT_SHA:-local}
    restart: unless-stopped
    env_file: .env.production.local      # runtime server secrets, chmod 600, not committed
    environment:
      DEPLOYMENT_VERSION: ${GIT_SHA:-local}
    ports:
      - "127.0.0.1:3000:3000"            # only nginx on the host can reach it
    volumes:
      - next-cache:/app/.next/cache      # ISR + optimized images survive restarts
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://127.0.0.1:3000/api/health"]
      interval: 30s
      timeout: 5s
      retries: 3
    stop_grace_period: 30s               # let in-flight requests and after() finish
secrets:
  actions_key:
    file: ./secrets/actions_key          # openssl rand -base64 32 > secrets/actions_key
volumes:
  next-cache:
```

Minimal health route:

```ts
// app/api/health/route.ts
export const dynamic = 'force-dynamic'
export function GET() {
  return Response.json({ ok: true })
}
```

## nginx

```nginx
upstream nextjs {
    server 127.0.0.1:3000;
    keepalive 32;
}

server {
    listen 80;
    listen [::]:80;
    server_name example.com www.example.com;
    return 301 https://example.com$request_uri;
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;
    http2 on;
    server_name example.com;

    ssl_certificate     /etc/letsencrypt/live/example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;

    client_max_body_size 5m;     # >= serverActions.bodySizeLimit
    gzip on;
    gzip_types text/css application/javascript application/json image/svg+xml;

    # Hashed build assets: cache forever (Next.js already sends immutable; this adds edge-level caching)
    location /_next/static/ {
        proxy_pass http://nextjs;
        proxy_set_header Host $host;
        expires 1y;
        add_header Cache-Control "public, max-age=31536000, immutable";
        access_log off;
    }

    location / {
        proxy_pass http://nextjs;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_buffering off;              # streaming / Suspense
        proxy_read_timeout 60s;
    }
}
```

- Server Actions compare the `Origin` header with `X-Forwarded-Host`/`Host`; forwarding the
  public host avoids "Invalid Server Actions request". Only when the proxy must send another
  host, list the public host in `experimental.serverActions.allowedOrigins`.
- Set `next start --keepAliveTimeout` (or the standalone server's equivalent via a custom
  server) higher than the upstream keepalive timeout of any load balancer in front.
- Test and reload: `sudo nginx -t && sudo systemctl reload nginx` (ask first).

## systemd (no Docker)

```ini
# /etc/systemd/system/nextjs.service
[Unit]
Description=Next.js app
After=network.target

[Service]
Type=simple
User=nextjs
WorkingDirectory=/srv/app/current
Environment=NODE_ENV=production
Environment=PORT=3000
Environment=HOSTNAME=127.0.0.1
EnvironmentFile=/srv/app/shared/.env.production.local
ExecStart=/usr/bin/node server.js
Restart=on-failure
KillSignal=SIGTERM
TimeoutStopSec=30
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=/srv/app/current/.next/cache

[Install]
WantedBy=multi-user.target
```

Release layout: build in CI, upload `standalone/` + `.next/static` + `public` to
`/srv/app/releases/<sha>`, point the `current` symlink at it, `systemctl restart nextjs`.
Keep `.next/cache` on a shared path if you want ISR and image caches to survive releases.

## Static export

```ts
const nextConfig = { output: 'export', images: { unoptimized: true }, trailingSlash: true }
```

```nginx
server {
    root /var/www/example/out;
    location /_next/static/ { expires 1y; add_header Cache-Control "public, max-age=31536000, immutable"; }
    location / { try_files $uri $uri.html $uri/ =404; }
    error_page 404 /404.html;
}
```
