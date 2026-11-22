# Bundle, images, fonts and scripts

## Ship less JavaScript

1. **Server Components first.** Markdown rendering, syntax highlighting, date formatting,
   data transformation: do it on the server; the library never reaches the browser.
2. **Lazy-load what is not needed for first paint:**
   ```tsx
   import dynamic from 'next/dynamic'
   const Chart = dynamic(() => import('@/components/Chart'), {
     ssr: false,                       // only inside Client Components
     loading: () => <div className="h-64 animate-pulse" />,
   })
   ```
   Good candidates: charts, editors, maps, video players, modals, emoji pickers, admin-only panels.
3. **Load on interaction:**
   ```ts
   async function onExport() {
     const { utils, writeFile } = await import('xlsx')
     // ...
   }
   ```
4. **Barrel imports.** `import { Delete } from '@mui/icons-material'` can pull in thousands of
   modules. Next.js optimises many popular packages automatically; add others with:
   ```ts
   // next.config.ts
   experimental: { optimizePackageImports: ['my-icon-lib', '@acme/ui'] }
   ```
5. **Replace heavy libraries:**

   | Heavy | Lighter |
   | --- | --- |
   | moment | date-fns, dayjs, `Intl.DateTimeFormat` |
   | lodash (full) | lodash-es per function, native methods |
   | axios | `fetch` |
   | crypto-js | Web Crypto (`crypto.subtle`) |
   | uuid | `crypto.randomUUID()` |
   | classnames | `clsx` (tiny) or template strings |
   | jQuery | DOM APIs |

6. **Duplicates.** Two versions of the same package ship twice. `npm ls <pkg>`, then
   `npm dedupe` or `overrides` (npm) / `pnpm.overrides`.
7. **Polyfills.** Next.js already includes polyfills for its supported browsers; remove
   `core-js` imports and legacy `browserslist` targets unless you support old browsers.

## Analysers

- Next.js 16.1+: `npx next analyze` (Turbopack; interactive, filters by route, shows import
  chains). `npx next analyze --output` writes data to `.next/diagnostics/analyze`.
- webpack builds: `@next/bundle-analyzer`
  ```js
  const withBundleAnalyzer = require('@next/bundle-analyzer')({ enabled: process.env.ANALYZE === 'true' })
  module.exports = withBundleAnalyzer(nextConfig)
  ```
  `ANALYZE=true npx next build --webpack` produces HTML reports in `.next/analyze/`.
- Without either: `python3 scripts/bundle_report.py --next-dir .next` measures real chunk
  sizes and per-route totals from the build manifests when they exist.

## Images (next/image)

- Always set `width`/`height` (or `fill` with a sized parent) to prevent CLS.
- `sizes` is essential with `fill` or responsive layouts; without it the browser may
  download the largest variant: `sizes="(max-width: 768px) 100vw, 50vw"`.
- LCP image (hero): `preload` (Next.js 16; `priority` is deprecated there) or
  `loading="eager"` plus `fetchPriority="high"`. Only one or two per page.
- Next.js 16 default `qualities` is `[75]`; add values to `images.qualities` if you pass
  other `quality` props.
- Remote images need `images.remotePatterns` (exact hosts).
- Self-hosting: `sharp` handles optimisation; the cache lives in `.next/cache/images`
  (persist it across deploys if you can).

## Fonts (next/font)

```ts
import { Inter } from 'next/font/google'
const inter = Inter({ subsets: ['latin'], display: 'swap', variable: '--font-inter' })
```

Self-hosted at build time (no request to Google at runtime), size-adjusted fallback reduces
CLS. Load only the weights and subsets you use; prefer variable fonts.

## Third-party scripts (next/script)

| Strategy | Use for |
| --- | --- |
| `beforeInteractive` | consent managers, bot detection that must run first (root layout only) |
| `afterInteractive` (default) | tag managers, analytics |
| `lazyOnload` | chat widgets, social embeds, feedback tools |
| `worker` (experimental, Partytown) | heavy third-party scripts off the main thread |

Audit every script: each tag manager container often loads 5-10 more scripts. Use
`@next/third-parties` for Google Tag Manager, Analytics, Maps and YouTube embeds.

## CSS

- Tailwind v4/v3 with content scanning keeps CSS small; avoid importing large CSS frameworks globally.
- CSS-in-JS runtimes (styled-components, Emotion) add JS and are client-only in App Router;
  prefer zero-runtime options for new code.

## Core Web Vitals cheat sheet

| Metric | Usual Next.js causes | Fixes |
| --- | --- | --- |
| LCP | hero image lazy-loaded, huge JS blocking render, slow TTFB from dynamic rendering | `preload` the hero, static/PPR shell, cache data |
| INP | big re-renders on input, heavy event handlers, hydration of large trees | transitions, deferred values, smaller client trees, yield long tasks |
| CLS | images/ads without dimensions, late web fonts, content injected above existing content | sizes on media, next/font, reserve space for banners |
