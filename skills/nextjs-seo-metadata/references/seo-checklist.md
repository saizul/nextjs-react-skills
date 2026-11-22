# Pre-launch SEO checklist for Next.js

## Every indexable page

- [ ] Unique `<title>`, about 30-60 characters, primary topic first, brand via template
- [ ] Unique meta description, about 70-160 characters, written for humans
- [ ] Absolute canonical URL pointing to itself (or the preferred duplicate)
- [ ] One `<h1>` that matches the page topic
- [ ] `og:title`, `og:description`, `og:image` (absolute, 1200x630), `twitter:card`
- [ ] Returns 200; moved pages 308 via `redirects()` in next.config or `permanentRedirect()`
- [ ] Not blocked by robots.txt and no accidental `noindex`

## Site-wide

- [ ] `<html lang>` set (and per-locale in `app/[lang]/layout.tsx`)
- [ ] `metadataBase` set from the production URL
- [ ] `/sitemap.xml` lists only canonical 200 URLs; referenced in robots.txt
- [ ] `/robots.txt` allows production; staging and preview deployments are noindex
- [ ] One host: `www` vs apex and `http` -> `https` redirect at the proxy/CDN
- [ ] Trailing slash policy consistent (`trailingSlash` in next.config) and canonicals match it
- [ ] Custom `not-found.tsx` returns 404; soft-404 pages avoided
- [ ] Favicon and `apple-icon` via file conventions (`app/icon.png`, `app/apple-icon.png`)
- [ ] `manifest.ts` if the site is installable

## Content and rendering

- [ ] Important content is server-rendered (not fetched in `useEffect`); check `view-source:`
- [ ] Links are real `<Link href>` / `<a href>` elements, not `onClick` navigation
- [ ] Images use `next/image` with descriptive `alt`, explicit sizes, `preload` (16+) or
      `priority` (15) only on the LCP image
- [ ] Pagination: each page has its own canonical (do not canonicalise page 2 to page 1)
- [ ] Faceted/filter URLs (`?color=red&sort=price`) canonicalise to the base listing or are noindex

## Structured data

| Page type | schema.org type | Required-ish fields |
| --- | --- | --- |
| Home | Organization / WebSite | name, url, logo |
| Article/blog post | Article / BlogPosting | headline, image, datePublished, author |
| Product | Product + Offer | name, image, offers.price, priceCurrency, availability |
| FAQ | FAQPage | mainEntity[].name, acceptedAnswer.text |
| Breadcrumbs | BreadcrumbList | itemListElement[].position, name, item |
| Local business | LocalBusiness | name, address, telephone, openingHours |

Validate with the Rich Results Test; JSON-LD must parse (the auditor's SEO015 rule).

## International

- [ ] `alternates.languages` reciprocal on every localized page, plus `x-default`
- [ ] Locale in the URL path (`/de/...`), not only in cookies or `Accept-Language`
- [ ] Localized titles, descriptions and OG images

## After launch

- Submit the sitemap in Google Search Console and Bing Webmaster Tools
- Watch Coverage/Page indexing for "Duplicate without user-selected canonical",
  "Crawled - currently not indexed" and soft 404s
