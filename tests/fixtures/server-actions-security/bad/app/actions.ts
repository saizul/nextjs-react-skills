'use server'
import { redirect } from 'next/navigation'
import { auth } from '@/auth'
import { db } from '@/lib/db'

export async function deletePost(id: string) {
  await db.post.delete({ where: { id } })
}

export async function login(prevState: unknown, formData: FormData) {
  const email = formData.get('email') as string
  const password = formData.get('password') as string
  await db.session.create({ data: { email, password } })
  redirect(formData.get('next') as string)
}

export const updateProfile = async (formData: FormData) => {
  const session = await auth()
  try {
    await db.user.update({ where: { id: session?.user.id }, data: { name: formData.get('name') } })
  } catch (e) {
    return { error: e.message }
  }
}

export async function refreshFeed() {
  // no input, but no auth either
  return db.post.findMany()
}
