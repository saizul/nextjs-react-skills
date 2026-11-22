---
name: nextjs-seo-metadata
description: Set up and audit SEO for Next.js App Router sites - the Metadata API (metadata, generateMetadata, title templates, metadataBase, canonical and hreflang alternates, robots), sitemap.ts, robots.ts, opengraph-image / twitter-image files and ImageResponse, and JSON-LD structured data. Includes an offline auditor that checks built HTML (out/ or .next/server/app) for missing titles, descriptions, canonicals, Open Graph tags, lang, invalid JSON-LD and duplicates, or checks app/ source for pages without metadata, dynamic routes without generateMetadata, missing metadataBase, sitemap and robots files and robots rules that block the whole site. Use when the user asks to add or fix SEO, meta tags, Open Graph or social previews, sitemaps, robots.txt, canonical URLs, structured data or rich results in a Next.js app, or asks why a page has the wrong title or no preview image when shared.
license: MIT
compatibility: Next.js 14-16 App Router. Script needs Python 3.8+ only and never fetches URLs.
metadata:
  author: Saizul Amin
  version: "0.1.0"
---

# Next.js SEO and metadata

Every indexable page gets a unique title, description, absolute canonical URL and social
image, produced by the Metadata API (never hand-written `<head>` tags). The site exposes a
sitemap and robots rules that do not block production.

Paths below are relative to this skill's folder (in Claude Code: `${CLAUDE_SKILL_DIR}`).

## When to use

- "Add SEO / meta tags / Open Graph to my Next.js site", "shared link shows no image"
- Creating `sitemap.ts`, `robots.ts`, `opengraph-image.tsx`, JSON-LD for products, articles, FAQs
- "All my blog posts have the same title", "canonical points to localhost"
- A pre-launch SEO check of an exported (`output: 'export'`) or built site

## When not to use

- Pages Router (`next/head`, `next-seo`): concepts carry over, APIs differ
- Content strategy, keyword research or backlink work
- Live crawling, Search Console data or Core Web Vitals field data (use those tools);
  page speed is covered by `react-performance-review`

## Workflow

1. **Read the root layout and config.** Open `app/layout.tsx` and `next.config.*`. Note
   the production domain (ask if unknown), locales, and whether `output: 'export'` is used.
2. **Audit the source (read-only).**
   ```bash
   python3 scripts/seo_audit.py source .
   python3 scripts/seo_audit.py source . --json
   ```
   Rules: SEO020 metadata in a client file, SEO021 dynamic route without generateMetadata,
   SEO022 page without metadata, SEO023 manual `<title>`, SEO024 unescaped JSON-LD,
   SEO025 no metadataBase, SEO026/027/028 no sitemap/robots/OG image, SEO029 robots blocks `/`.
3. **Audit built HTML when a build exists** (catches what source analysis cannot: final
   titles after templates, resolved canonicals, broken JSON-LD):
   ```bash
   npx next build                                   # or use an existing build
   python3 scripts/seo_audit.py html .next/server/app
   python3 scripts/seo_audit.py html out            # static export
   ```
   Only prerendered pages have HTML files; dynamic (`ƒ`) routes need a running server (view
   source in the browser, or `curl -s http://localhost:3000/path`) and a manual check.
4. **Fix in this order** using [references/metadata-recipes.md](references/metadata-recipes.md):
   1. robots blocking production (SEO029) and noindex leaks
   2. `metadataBase` + title template + default description and OG image in the root layout
   3. `generateMetadata` for every dynamic route (title, description, canonical, OG image)
   4. `app/sitemap.ts` and `app/robots.ts`
   5. JSON-LD for the page types that have rich results (Product, Article, FAQPage,
      BreadcrumbList, Organization), escaped with `.replace(/</g, '\\u003c')`
5. **Show diffs and wait for approval** before editing; metadata changes affect search
   results for every page.
6. **Verify.** Re-run both audits. Then check a few URLs: `view-source:` for tags,
   `/sitemap.xml` and `/robots.txt` in the browser, the Rich Results Test and a social
   preview debugger for one page of each template.

## Output

```
SEO audit (source + 24 built pages)
High
- app/robots.ts disallows '/' for all crawlers -> gate on VERCEL_ENV/APP_ENV instead
Medium
- 18 blog pages share the title "Acme" -> generateMetadata in app/blog/[slug]/page.tsx
- no metadataBase -> canonical and og:image resolve to http://localhost:3000
Low
- 6 pages have descriptions under 50 characters
Proposed changes: app/layout.tsx (metadataBase, template), app/blog/[slug]/page.tsx
(generateMetadata), new app/sitemap.ts, app/robots.ts. Diff below.
```

## Checklist

See [references/seo-checklist.md](references/seo-checklist.md) for the full pre-launch list
(titles, descriptions, canonicals, hreflang, pagination, 404 handling, images, structured data).
