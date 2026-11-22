import Image from 'next/image'
import Link from 'next/link'
import { XIcon } from './icons'

export function Bad({ onClose, go }: { onClose: () => void; go: () => void }) {
  return (
    <div>
      <img src="/hero.png" />
      <Image src="/team.jpg" width={400} height={300} />
      <img src="/logo.png" alt="image of logo" />
      <div onClick={onClose}>Close</div>
      <span role="button" onClick={go}>Go</span>
      <a onClick={go}>Next page</a>
      <a href="#" onClick={go}>Back</a>
      <button onClick={onClose}>
        <XIcon />
      </button>
      <Link href="/cart"><CartIcon /></Link>
      <input type="email" placeholder="Email" />
      <select name="country"><option>BD</option></select>
      <input type="text" tabIndex={3} autoFocus />
      <button aria-hidden="true">Hidden</button>
      <iframe src="https://maps.example.com/embed" />
    </div>
  )
}
