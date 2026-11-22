export const metadata = { title: 'Acme', description: 'Invoicing' }

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html>
      <body>{children}</body>
    </html>
  )
}
