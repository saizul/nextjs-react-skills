import { db } from '@/lib/db'

export function LikeButton({ postId }: { postId: string }) {
  async function like(formData: FormData) {
    'use server'
    await db.like.create({ data: { postId: formData.get('postId') } })
  }
  return (
    <form action={like}>
      <input type="hidden" name="postId" value={postId} />
      <button>Like</button>
    </form>
  )
}
