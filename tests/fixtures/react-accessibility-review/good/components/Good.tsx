import { useState } from 'react'
import Image from 'next/image'
import Link from 'next/link'
import { XIcon } from './icons'

type Props = { onClose: () => void; label: string; inputProps: React.ComponentProps<'input'> }

export function Good({ onClose, label, inputProps }: Props) {
  const [email, setEmail] = useState<string>('')
  const items = new Map<string, number>()
  return (
    <div>
      <img src="/hero.png" alt="Two people reviewing an invoice on a laptop" />
      <Image src="/divider.svg" alt="" width={400} height={4} />
      <button type="button" onClick={onClose} aria-label="Close dialog">
        <XIcon />
      </button>
      <button type="button" onClick={onClose}>
        <XIcon /> <span className="sr-only">Close</span>
      </button>
      <button type="submit">{label}</button>
      <Link href="/cart">Cart ({items.size})</Link>
      <p>Don't worry, we never share your email.</p>
      <label htmlFor="email">Email</label>
      <input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
      <label>
        Country
        <select name="country"><option>BD</option></select>
      </label>
      <input aria-label="Search" type="search" />
      <input type="hidden" name="token" value="x" />
      <input {...inputProps} />
      <div role="button" tabIndex={0} onClick={onClose} onKeyDown={(e) => e.key === 'Enter' && onClose()}>
        Custom
      </div>
      <iframe title="Office location map" src="https://maps.example.com/embed" />
      {email.length > 3 && <span>Looks good</span>}
    </div>
  )
}
