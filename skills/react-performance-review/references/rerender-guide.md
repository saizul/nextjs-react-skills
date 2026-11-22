# Re-render guide

A component re-renders when its parent re-renders, its state changes, or a context it reads
changes. Re-rendering is usually cheap; it is a problem only when a render is expensive or
happens very often (every keystroke, scroll or animation frame).

## Causes and fixes

| Cause | Symptom | Fix |
| --- | --- | --- |
| State lives too high | typing in one field re-renders the whole page | move state down into the component that uses it |
| Context value is a new object each render | every consumer re-renders on any provider render | `useMemo` the value, or split into state and dispatch contexts |
| One big context for everything | theme change re-renders the cart | split contexts by update frequency; or use a selector store (Zustand, Jotai) |
| New object/array/function props | `React.memo` child still re-renders | hoist constants out of the component; `useMemo`/`useCallback` only for memoised children |
| Derived state stored in `useState` + `useEffect` | extra render pass, flicker | compute during render (`const visible = items.filter(...)`) |
| Expensive computation in render | slow renders shown in Profiler | `useMemo(() => compute(a, b), [a, b])` |
| Index or random `key` | inputs lose focus, rows remount | stable ids as keys |
| Long lists | thousands of DOM nodes | virtualise (react-window, TanStack Virtual); paginate |
| Urgent and non-urgent updates mixed | input lags while results render | `useDeferredValue(query)` or `startTransition(() => setResults(...))` |
| Effects that set state on every render | render loops, warnings | fix dependencies; use an event handler instead of an effect |
| Unstable `useSearchParams`-driven state | navigation re-renders whole tree | read params in the leaf that needs them |
| Animations through React state | 60 renders per second | CSS transitions, or refs + `requestAnimationFrame` |

## When memoisation helps

- `React.memo(Component)`: the component renders often with the same props and is
  expensive. Useless if a prop is a new object/function every time.
- `useMemo`: the computation is measurably slow (> ~1 ms) or the result is passed to a
  memoised child / used as an effect dependency.
- `useCallback`: the function is passed to a memoised child or used as an effect dependency.
- Otherwise memoisation adds code and comparison cost without a benefit.

## React Compiler

Next.js 16 supports `reactCompiler: true` (stable, opt-in; needs `babel-plugin-react-compiler`,
builds get slower). It memoises components and values automatically when code follows the
Rules of React (pure render, no mutation of props/state, hooks at top level).

- Enable it in a branch, run the test suite and click through critical flows.
- Keep `eslint-plugin-react-hooks` (the compiler lint rules ship in it) to find code the
  compiler skips.
- Manual `useMemo`/`useCallback` can stay; remove them gradually where profiling shows no change.

## Profiling recipe

1. React DevTools > Profiler > settings: "Record why each component rendered while profiling".
2. Record the slow interaction once. Sort by "Ranked"; look at the widest bars.
3. For each hot component, read "Why did this render?": props changed (which), hooks
   changed, parent rendered.
4. Chrome Performance panel with CPU 4x slowdown: long tasks (> 50 ms) in the interaction
   are what INP measures. Look for scripting time inside event handlers and React commits.
5. In production, measure with `useReportWebVitals` (next/web-vitals) or the `web-vitals`
   library and send INP attribution to your analytics.

```tsx
'use client'
import { useReportWebVitals } from 'next/web-vitals'

export function WebVitals() {
  useReportWebVitals((metric) => {
    navigator.sendBeacon('/api/vitals', JSON.stringify(metric))
  })
  return null
}
```

## Hydration cost

Large Client Components hydrate on load even if the user never touches them. Ways to cut it:
- Keep static content in Server Components (no hydration).
- Lazy-load interactive widgets that are below the fold or behind a click.
- Avoid wrapping the whole app in a client provider that forces heavy libraries to load.
