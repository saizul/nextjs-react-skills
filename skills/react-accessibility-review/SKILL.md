---
name: react-accessibility-review
description: Review and fix accessibility (a11y, WCAG 2.2 AA) in React and Next.js components - images without alt text, div/span click handlers instead of buttons, links used as buttons, icon-only buttons without accessible names, form fields without labels, positive tabIndex, autoFocus, aria-hidden on focusable elements, missing html lang, iframes without title, plus manual checks for focus management in dialogs and route changes, keyboard navigation, color contrast, live regions, reduced motion and accessible form errors. Includes a static JSX/TSX scanner and recipes for axe, eslint-plugin-jsx-a11y and Playwright checks. Use when the user asks to make components accessible, fix a11y lint errors or Lighthouse accessibility issues, prepare for a WCAG or ADA/EAA audit, review a component library, or asks whether a custom button, modal, dropdown or form is screen-reader and keyboard friendly.
license: MIT
compatibility: React 18-19, Next.js 13-16 (JSX/TSX). Script needs Python 3.8+ only.
metadata:
  author: Saizul Amin
  version: "0.1.0"
---

# React accessibility review

Use native elements first (`<button>`, `<a href>`, `<label>`, `<dialog>`), ARIA second. A
static scan finds about a third of real issues; the keyboard and screen-reader pass in
this workflow finds most of the rest.

Paths below are relative to this skill's folder (in Claude Code: `${CLAUDE_SKILL_DIR}`).

## When to use

- "Make this component accessible", "fix the a11y lint warnings", Lighthouse a11y < 100
- Reviewing custom buttons, menus, modals, tabs, comboboxes, forms
- Preparing for a WCAG 2.2 AA audit, ADA or European Accessibility Act requirements
- A user reports they cannot use the site with a keyboard or screen reader

## When not to use

- Formal conformance certification (needs a human audit with assistive technology)
- Native mobile apps (React Native has different APIs)
- Pure visual design review beyond contrast and focus visibility

## Workflow

1. **Run the static scan (read-only).**
   ```bash
   python3 scripts/a11y_scan.py .                  # whole project
   python3 scripts/a11y_scan.py components/Modal.tsx
   python3 scripts/a11y_scan.py . --json --fail-on high
   ```
   Rules: A11Y001 missing alt, A11Y002 redundant alt, A11Y003 click on non-interactive
   element, A11Y004/005 role without tabIndex/keyboard handler, A11Y006 link as button,
   A11Y007 no accessible name, A11Y008 field without label, A11Y009 positive tabIndex,
   A11Y010 autoFocus, A11Y011 aria-hidden on focusable, A11Y012 html without lang,
   A11Y013 iframe without title. Spread props (`{...props}`) are treated as "may provide it".
2. **Check the lint setup.** If ESLint is used, recommend `eslint-plugin-jsx-a11y`
   (recommended config) so new issues fail in the editor and CI.
3. **Fix findings** with [references/fix-patterns.md](references/fix-patterns.md). Typical:
   `<div onClick>` -> `<button type="button">`; icon button -> `aria-label` or visually hidden
   text; placeholder-only input -> `<label htmlFor>`; decorative image -> `alt=""`.
   Show diffs and keep visual styling identical (reset button styles with CSS, do not
   keep the div).
4. **Review what the scanner cannot see** (checklist in fix-patterns.md): focus moves into
   and is trapped in dialogs and returns on close; visible focus styles; heading order;
   color contrast 4.5:1 for text; error messages linked with `aria-describedby` and
   announced; loading states announced; `prefers-reduced-motion`; target size 24x24 px.
5. **Run automated rendered checks** from [references/testing-a11y.md](references/testing-a11y.md):
   `@axe-core/playwright` on key pages, or `vitest-axe`/`jest-axe` in component tests.
6. **Do a keyboard pass** and describe it: Tab through the page, operate every control with
   Enter/Space/Escape/arrow keys, confirm nothing is unreachable and focus is always visible.
   Suggest a quick screen reader check (VoiceOver: Cmd+F5 on macOS; NVDA on Windows).

## Output

```
Accessibility review: components/ (42 files)
High (blocks keyboard / screen-reader users)
- Header.tsx:31 <div onClick={openMenu}> -> <button type="button" aria-expanded={open} aria-controls="menu">
- CartButton.tsx:12 icon-only <button> without a name -> aria-label="Open cart (3 items)"
Medium
- Newsletter.tsx:8 <input placeholder="Email"> without label -> <label className="sr-only" htmlFor="nl-email">
Manual findings
- Modal: focus stays on the page behind the dialog -> use <dialog> with showModal() or a focus trap
Automated: axe on /, /pricing, /checkout: 0 violations after fixes
```

## Principles

- No ARIA is better than wrong ARIA. `role="button"` on a div still needs tabIndex,
  Enter/Space handling and focus styles; a `<button>` has all of them.
- Links navigate (`<Link href>`), buttons act. Never `href="#"` with onClick.
- Every form control has a visible label; placeholders disappear and are not labels.
- Do not remove focus outlines without a visible replacement (`:focus-visible`).
