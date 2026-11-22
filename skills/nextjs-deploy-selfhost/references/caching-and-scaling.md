# Caching and scaling a self-hosted Next.js app

## What Next.js sends

| Response | Cache-Control | Proxy/CDN may cache? |
| --- | --- | --- |
| `/_next/static/*` (hashed) | `public, max-age=31536000, immutable` | yes, forever |
| Static image imports, optimized images | `public, max-age=...` (images: `minimumCacheTTL`, default 4 h in 16) | yes |
| Fully static (prerendered) pages | `s-maxage=..., stale-while-revalidate` / `public` | yes, respecting the header |
| ISR pages | `s-maxage=<revalidate>, stale-while-revalidate` | yes, respecting the header |
| Dynamic pages (cookies/headers/uncached data) | `private, no-cache, no-store, max-age=0, must-revalidate` | **no** |
| RSC payload requests (`RSC: 1` header, `_rsc` query) | varies | only if the cache key includes the RSC headers; safest not to cache |

Rules for nginx `proxy_cache` or a CDN:
- Respect upstream `Cache-Control`; never `proxy_ignore_headers Cache-Control` on app routes.
- Do not cache responses that set cookies.
- Cache keys must vary on the headers Next.js uses for RSC (`RSC`, `Next-Router-State-Tree`,
  `Next-Router-Prefetch`) or bypass caching when they are present; otherwise HTML and RSC
  payloads get mixed up during client navigation.

## Single instance (most VPS setups)

Works out of the box: the ISR/data cache lives in memory (50 MB default) and on disk in
`.next/cache`. Mount `.next/cache` on a volume so it survives container restarts and
deploys of the same build.

## Multiple instances

| Problem | Symptom | Fix |
| --- | --- | --- |
| Each instance has its own cache | page shows old data on some requests | `cacheHandler` (ISR/fetch cache) and `cacheHandlers` (`'use cache'`) backed by Redis; `cacheMaxMemorySize: 0` |
| Tag invalidation only on one instance | `revalidateTag` "does not work" | handler implements tag index in shared store; `refreshTags()` for `'use cache'` handlers |
| Different Server Action keys per build | `Failed to find Server Action` | same `NEXT_SERVER_ACTIONS_ENCRYPTION_KEY` (base64, 16/24/32 bytes) at build time for all instances |
| Different builds during rolling deploy | missing chunks, failed navigations | build once, run the same image everywhere; set `deploymentId` (skew detection triggers a hard reload) |
| Rebuilding per environment | different build IDs | `generateBuildId: () => process.env.GIT_SHA` |
| Images optimized per instance | CPU spikes after deploy | shared cache volume, or a dedicated image service / CDN loader |

```ts
// next.config.ts (multi-instance)
const nextConfig = {
  output: 'standalone',
  deploymentId: process.env.DEPLOYMENT_VERSION,
  cacheHandler: require.resolve('./cache-handler.js'),
  cacheMaxMemorySize: 0,
}
```

Use a maintained Redis handler (see the Next.js `cache-handler-redis` example and the
community handlers listed in its README) rather than writing one from scratch; handlers must
serialize `Buffer`/`Map` values, bound their size and handle connection errors.

Generate the encryption key once and store it as a CI secret:

```bash
openssl rand -base64 32
```

## Graceful shutdown

Send `SIGTERM` (Docker does by default) and allow 10-30 s (`stop_grace_period`,
`TimeoutStopSec`): Next.js finishes in-flight requests and pending `after()` callbacks.
Behind a load balancer, remove the instance from rotation (failing health check) before
stopping it.

## Image optimization

- `sharp` is used automatically when present; on glibc Linux with high memory use, consider
  `MALLOC_ARENA_MAX=2` or jemalloc as the sharp docs suggest.
- Next.js 16: local images with query strings need `images.localPatterns`; local IP upstreams
  are blocked unless `images.dangerouslyAllowLocalIP` (private networks only); max 3 redirects.
- `remotePatterns` with `hostname: '**'` turns `/_next/image` into an open proxy that anyone
  can use to make your server fetch and resize arbitrary images; list exact hosts.

## Static export vs server

Static export (`output: 'export'`) supports: Server Components at build time, client
components, `generateStaticParams`, GET route handlers that are static, metadata files.
Not supported: Server Actions, dynamic route handlers, `cookies()`/`headers()`, proxy.ts,
ISR/revalidation, `next/image` default loader, rewrites/redirects/headers in next.config
(configure them in nginx instead).

## Observability

- `instrumentation.ts` `register()` for OpenTelemetry (`@vercel/otel` works self-hosted).
- Log in JSON to stdout; let Docker/journald collect.
- Watch for `ECONNRESET` / 502 bursts: keep-alive timeout mismatch between nginx/LB and Node.
