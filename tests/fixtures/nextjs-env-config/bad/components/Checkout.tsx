'use client'

export function Checkout({ key }: { key: string }) {
  const db = process.env.DATABASE_URL
  const api = process.env.NEXT_PUBLIC_API_URL
  const anything = process.env[key]
  const { NEXT_PUBLIC_STRIPE_SECRET_KEY } = process.env
  return <a href={api}>{db}{anything}{NEXT_PUBLIC_STRIPE_SECRET_KEY}</a>
}
