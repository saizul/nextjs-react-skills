'use client'
import { useState } from 'react'

export function Counter({ initial }: { initial: number }) {
  const [n, setN] = useState(initial)
  return <button onClick={() => setN(n + 1)}>{n}</button>
}
