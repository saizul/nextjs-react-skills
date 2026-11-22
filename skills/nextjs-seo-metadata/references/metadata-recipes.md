# Metadata recipes (App Router)

## Root layout

```tsx
// app/layout.tsx
import type { Metadata, Viewport } from 'next'

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? 'https://example.com'),
  title: { default: 'Acme - Invoicing for small teams', template: '%s | Acme' },
  description: 'Send invoices, track payments and chase late clients automatically.',
  applicationName: 'Acme',
  openGraph: { type: 'website', siteName: 'Acme', locale: 'en_US' },
  twitter: { card: 'summary_large_image' },
  alternates: { canonical: '/' },
}

export const viewport: Viewport = { themeColor: '#0f172a' }

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
```

- `metadataBase` makes relative `canonical`, `openGraph.images` and `alternates` absolute.
  Without it Next.js falls back to `http://localhost:3000` (and warns at build time).
- Child segments that set `title: 'Pricing'` render `Pricing | Acme`. Use
  `title: { absolute: '...' }` to skip the template.
- `openGraph` is shallow-merged per segment: a page that sets `openGraph: { title }` drops the
  layout's `openGraph.images` unless it repeats them. Put the default image in
  `app/opengraph-image.png` (file convention) so it is always inherited.

## Static page

```tsx
export const metadata: Metadata = {
  title: 'Pricing',
  description: 'Plans from $0 for freelancers to $49/month for agencies. Cancel any time.',
  alternates: { canonical: '/pricing' },
}
```

## Dynamic route

```tsx
// app/blog/[slug]/page.tsx
import type { Metadata } from 'next'
import { notFound } from 'next/navigation'
import { cache } from 'react'

const getPost = cache(async (slug: string) => db.post.findUnique({ where: { slug } }))

type Props = { params: Promise<{ slug: string }> }

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params
  const post = await getPost(slug)
  if (!post) return { title: 'Not found', robots: { index: false } }
  return {
    title: post.title,
    description: post.excerpt,
    alternates: { canonical: `/blog/${slug}` },
    openGraph: {
      type: 'article',
      title: post.title,
      description: post.excerpt,
      publishedTime: post.publishedAt.toISOString(),
      images: [{ url: post.coverUrl, width: 1200, height: 630, alt: post.coverAlt }],
    },
  }
}

export default async function PostPage({ params }: Props) {
  const { slug } = await params
  const post = await getPost(slug) // deduped with generateMetadata by cache()
  if (!post) notFound()
  return <article>...</article>
}
```

## sitemap.ts

```ts
// app/sitemap.ts
import type { MetadataRoute } from 'next'

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const base = 'https://example.com'
  const posts = await db.post.findMany({ select: { slug: true, updatedAt: true } })
  return [
    { url: base, lastModified: new Date(), changeFrequency: 'weekly', priority: 1 },
    { url: `${base}/pricing`, lastModified: new Date() },
    ...posts.map((p) => ({ url: `${base}/blog/${p.slug}`, lastModified: p.updatedAt })),
  ]
}
```

More than 50,000 URLs: split with `generateSitemaps()` (one sitemap per id). Only list
canonical, indexable, 200-status URLs.

## robots.ts (safe for staging)

```ts
// app/robots.ts
import type { MetadataRoute } from 'next'

export default function robots(): MetadataRoute.Robots {
  const isProd = process.env.APP_ENV === 'production'
  if (!isProd) return { rules: { userAgent: '*', disallow: '/' } }
  return {
    rules: { userAgent: '*', allow: '/', disallow: ['/admin/', '/api/'] },
    sitemap: 'https://example.com/sitemap.xml',
  }
}
```

The auditor reports SEO029 as medium on this file because it cannot evaluate the condition;
confirm the production branch is taken (`curl https://example.com/robots.txt`) and note it as accepted.
Robots rules do not remove pages from the index; use `robots: { index: false }` metadata
(noindex) for that, and do not also block the URL in robots.txt (crawlers must see the tag).

## Open Graph image

File conventions: `opengraph-image.(png|jpg)` or `opengraph-image.tsx` in any segment, plus
`twitter-image.*`. Generated image:

```tsx
// app/blog/[slug]/opengraph-image.tsx
import { ImageResponse } from 'next/og'

export const size = { width: 1200, height: 630 }
export const contentType = 'image/png'
export const alt = 'Acme blog'

export default async function Image({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params
  const post = await getPost(slug)
  return new ImageResponse(
    <div style={{ display: 'flex', width: '100%', height: '100%', padding: 64, fontSize: 64, background: '#0f172a', color: 'white' }}>
      {post?.title ?? 'Acme'}
    </div>,
    size,
  )
}
```

Keep text large (social previews are small), 1200x630, under about 1 MB.

## JSON-LD

```tsx
export function JsonLd({ data }: { data: Record<string, unknown> }) {
  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(data).replace(/</g, '\\u003c') }}
    />
  )
}

// in a product page
<JsonLd
  data={{
    '@context': 'https://schema.org',
    '@type': 'Product',
    name: product.name,
    image: product.images,
    description: product.description,
    offers: { '@type': 'Offer', price: product.price, priceCurrency: 'USD', availability: 'https://schema.org/InStock' },
  }}
/>
```

The `<` escape stops a value such as `</script><script>...` from breaking out of the tag.
Mark up only content visible on the page. Validate with the Rich Results Test.

## Alternates for languages

```ts
alternates: {
  canonical: '/en/pricing',
  languages: { 'en-US': '/en/pricing', 'de-DE': '/de/preise', 'x-default': '/en/pricing' },
}
```

Every language version must list all others (reciprocal), and each canonical points to itself.

## Not-found and noindex

- `notFound()` returns a real 404 status; do not render "not found" text with status 200.
- Staging, preview and search-result pages: `robots: { index: false, follow: true }`.
