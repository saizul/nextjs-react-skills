import Image from 'next/image'
import { cookies } from 'next/headers'

export default async function Page() {
  const c = await cookies()
  return <Image src="/hero.png" alt="Hero" width={800} height={400} />
}
