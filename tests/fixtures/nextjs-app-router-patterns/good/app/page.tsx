import { Counter } from '@/components/Counter'

// Server Component: no useState( here, the counter is a client island.
export default async function Home() {
  const res = await fetch('https://api.example.com/stats', { next: { revalidate: 60 } })
  const stats = await res.json()
  return (
    <main>
      <h1>{stats.title}</h1>
      <Counter initial={stats.count} />
    </main>
  )
}
