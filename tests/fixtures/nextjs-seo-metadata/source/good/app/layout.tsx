import type { Metadata } from 'next'

export const metadata: Metadata = {
  metadataBase: new URL('https://example.com'),
  title: { default: 'Acme', template: '%s | Acme' },
  description: 'Invoicing for small teams',
  openGraph: { type: 'website', siteName: 'Acme' },
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
