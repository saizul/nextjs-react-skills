import { useState } from 'react'

export function useCart() {
  const [items, setItems] = useState<string[]>([])
  return { items, add: (id: string) => setItems((x) => [...x, id]) }
}
