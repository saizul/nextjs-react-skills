'use client'
import { useState } from 'react'

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false)
  return (
    <html lang="en">
      <body onClick={() => setOpen(!open)}>{children}</body>
    </html>
  )
}
