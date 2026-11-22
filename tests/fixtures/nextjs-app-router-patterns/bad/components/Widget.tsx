'use client'
import fs from 'fs'
import { revalidatePath } from 'next/cache'

export const metadata = { title: 'Widget' }

export default async function Widget() {
  const data = fs.readFileSync('/tmp/data.json', 'utf8')
  revalidatePath('/')
  return <div>{data}</div>
}
