import { cookies } from 'next/headers'
import { getPost } from '@/lib/posts'

export default async function Post({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params
  const theme = (await cookies()).get('theme')
  const post = await getPost(slug)
  return <article data-theme={theme?.value}>{post.title}</article>
}
