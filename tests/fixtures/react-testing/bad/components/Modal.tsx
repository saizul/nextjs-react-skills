'use client'
import { useEffect, useRef, useState } from 'react'

export function Modal({ onClose, title }: { onClose: () => void; title: string }) {
  const [open, setOpen] = useState(true)
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => ref.current?.focus(), [])
  return open ? (
    <div ref={ref} role="dialog" aria-label={title} onKeyDown={(e) => e.key === 'Escape' && onClose()}>
      <button onClick={() => setOpen(false)}>Hide</button>
      <button onClick={onClose}>Close</button>
    </div>
  ) : null
}
