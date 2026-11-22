import { z } from 'zod'
import { auth } from '@/auth'
import { db } from '@/lib/db'

const PostSchema = z.object({ title: z.string().min(1).max(200) })

export async function POST(request: Request) {
  const origin = request.headers.get('origin')
  if (origin !== process.env.APP_ORIGIN) return new Response('Forbidden', { status: 403 })
  const session = await auth()
  if (!session) return new Response('Unauthorized', { status: 401 })
  const data = PostSchema.parse(await request.json())
  return Response.json(await db.post.create({ data: { ...data, authorId: session.user.id } }))
}
