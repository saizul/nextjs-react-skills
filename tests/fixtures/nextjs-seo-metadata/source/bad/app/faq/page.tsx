export const metadata = { title: 'FAQ' }

export default function Faq({ items }: { items: { q: string; a: string }[] }) {
  const jsonLd = { '@context': 'https://schema.org', '@type': 'FAQPage', mainEntity: items }
  return (
    <>
      <title>FAQ</title>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
    </>
  )
}
