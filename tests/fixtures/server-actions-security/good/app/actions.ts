'use server'
import { z } from 'zod'
import { redirect } from 'next/navigation'
import { updateTag } from 'next/cache'
import { auth } from '@/auth'
import { db } from '@/lib/db'
import { ratelimit } from '@/lib/ratelimit'

const DeleteSchema = z.object({ id: z.string().uuid() })
const LoginSchema = z.object({ email: z.string().email(), password: z.string().min(8), next: z.string().optional() })

export async function deletePost(input: unknown) {
  const session = await auth()
  if (!session) throw new Error('Unauthorized')
  const { id } = DeleteSchema.parse(input)
  await db.post.delete({ where: { id, authorId: session.user.id } })
  updateTag('posts')
}

// action-scan: public (login must work for anonymous users)
export async function login(prevState: unknown, formData: FormData) {
  const { success } = await ratelimit.limit(String(formData.get('email')))
  if (!success) return { error: 'Too many attempts' }
  const parsed = LoginSchema.safeParse(Object.fromEntries(formData))
  if (!parsed.success) return { error: 'Invalid input' }
  const to = parsed.data.next ?? '/'
  redirect(to.startsWith('/') && !to.startsWith('//') ? to : '/')
}
