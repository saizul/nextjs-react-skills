# Accessibility fix patterns (React / Next.js)

## Clickable div -> button

```tsx
// before
<div className="card-action" onClick={onSelect}>Select</div>

// after
<button type="button" className="card-action" onClick={onSelect}>Select</button>
```

```css
/* keep the old look */
.card-action { all: unset; cursor: pointer; }
.card-action:focus-visible { outline: 2px solid currentColor; outline-offset: 2px; }
```

Whole clickable card linking somewhere: put a real `<Link>` on the title and stretch it with
a pseudo-element (`.card { position: relative } .card a::after { content: ''; position: absolute; inset: 0 }`).

## Icon-only button / link

```tsx
<button type="button" onClick={onClose} aria-label="Close dialog">
  <XIcon aria-hidden="true" focusable="false" />
</button>

<Link href="/cart">
  <CartIcon aria-hidden="true" />
  <span className="sr-only">Cart, {count} items</span>
</Link>
```

`sr-only` (Tailwind) or:
```css
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; border: 0; }
```

## Images

| Image | alt |
| --- | --- |
| Informative (product photo, chart) | what it shows / the key data |
| Functional (logo link, image button) | where it goes / what it does ("Acme home") |
| Decorative (divider, background flourish) | `alt=""` |
| Complex (diagram) | short alt + longer description nearby (`aria-describedby`) |

Do not start alt text with "image of"; screen readers already announce "image".

## Labels and errors

```tsx
<label htmlFor="email">Email</label>
<input
  id="email"
  name="email"
  type="email"
  autoComplete="email"
  required
  aria-invalid={!!error}
  aria-describedby={error ? 'email-error' : 'email-hint'}
/>
<p id="email-hint">We send the receipt here.</p>
{error && <p id="email-error" role="alert">{error}</p>}
```

- Use `useId()` for ids in reusable components.
- Group radios/checkboxes in `<fieldset><legend>`.
- On submit failure, move focus to the first invalid field or an error summary.

## Dialog (modal)

Prefer the native element:

```tsx
'use client'
import { useEffect, useRef } from 'react'

export function Modal({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: string; children: React.ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    const d = ref.current
    if (!d) return
    if (open && !d.open) d.showModal()   // focus trap, Escape, inert background built in
    if (!open && d.open) d.close()
  }, [open])
  return (
    <dialog ref={ref} aria-labelledby="modal-title" onClose={onClose}>
      <h2 id="modal-title">{title}</h2>
      {children}
      <button type="button" onClick={onClose}>Close</button>
    </dialog>
  )
}
```

Focus returns to the opener automatically with `showModal()`/`close()` in modern browsers.
Libraries (Radix UI, React Aria, Headless UI, shadcn/ui) implement dialogs, menus, comboboxes
and tabs correctly; prefer them to hand-rolled widgets.

## Disclosure / menu button

```tsx
<button type="button" aria-expanded={open} aria-controls="nav-menu" onClick={() => setOpen(!open)}>
  Menu
</button>
<ul id="nav-menu" hidden={!open}>...</ul>
```

## Live announcements

```tsx
<div aria-live="polite" className="sr-only">{status}</div>  {/* "3 results", "Saved" */}
```

Render the live region once (empty) and change its text; inserting it together with the
message is often not announced. Use `role="alert"` only for urgent errors.

## Route changes (Next.js)

Next.js App Router includes a route announcer that reads the new page title (or first h1).
Give every page a unique `title` and a single `<h1>`. For client-side filtering that does not
change the route, announce the result count with a live region.

## Skip link

```tsx
// app/layout.tsx
<body>
  <a href="#main" className="sr-only focus:not-sr-only">Skip to content</a>
  <Header />
  <main id="main" tabIndex={-1}>{children}</main>
</body>
```

## Motion

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; scroll-behavior: auto !important; }
}
```

In JS animation libraries, check `useReducedMotion()` (Motion) or `matchMedia('(prefers-reduced-motion: reduce)')`.

## Manual checklist (what the scanner cannot see)

- [ ] Every interactive element reachable and operable with keyboard only
- [ ] Focus visible everywhere (`:focus-visible` styles, not `outline: none`)
- [ ] Logical tab order (DOM order matches visual order)
- [ ] Dialogs trap focus, close on Escape, return focus to the trigger
- [ ] One `<h1>`; headings do not skip levels for styling
- [ ] Landmarks: `<header>`, `<nav>`, `<main>`, `<footer>`; one `<main>`
- [ ] Text contrast >= 4.5:1 (large text 3:1); UI component/focus indicator contrast >= 3:1
- [ ] Information not conveyed by color alone (errors have text/icons)
- [ ] Target size at least 24x24 CSS px (WCAG 2.2 2.5.8)
- [ ] Content reflows at 320 px width and 200% zoom without horizontal scrolling
- [ ] Form errors identified in text and linked to fields
- [ ] Videos have captions; audio has transcripts; no autoplay with sound
- [ ] Page `<title>` unique and `<html lang>` correct
