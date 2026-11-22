'use server'
import { revalidateTag, updateTag } from 'next/cache'

export async function publish() {
  revalidateTag('posts', 'max')
}

export async function rename(id: string) {
  updateTag(`post-${id}`)
}
