import { cookies } from 'next/headers'
import { getPost } from '@/lib/posts'

export default async function Post({ params }: { params: { slug: string } }) {
  const theme = cookies().get('theme')
  const post = await getPost(params.slug)
  return <article data-theme={theme?.value}>{post.title}</article>
}
