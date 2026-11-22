import { cookies } from 'next/headers'
import { db } from '@/lib/db'

export async function GET() {
  return Response.json(await db.post.findMany())
}

export async function POST(request: Request) {
  const token = (await cookies()).get('session')?.value
  const body = await request.json()
  const post = await db.post.create({ data: { ...body, token } })
  return Response.json(post)
}
