---
name: react-performance-review
description: Find and fix React and Next.js performance problems - unnecessary re-renders (unstable props, context fan-out, state too high, missing keys), when memo/useMemo/useCallback or the React Compiler actually help, JavaScript bundle size per route, code splitting with next/dynamic and lazy, heavy dependencies (moment, lodash, chart libraries, icon barrels), Server Components to cut client JS, next/image, next/font and third-party scripts, and Core Web Vitals (LCP, INP, CLS). Includes a report script that parses `next build` output (Next.js 13-15), webpack stats JSON, or a built .next directory and flags routes over a first-load JS budget, oversized chunks, heavy and duplicated packages. Use when the user says the app is slow, a page is janky or re-renders too much, Lighthouse or PageSpeed scores are low, INP/LCP/CLS are poor, the bundle is too big, or asks whether to use memo or useCallback.
license: MIT
compatibility: React 18-19, Next.js 13-16. Script needs Python 3.8+ only; it reads build output and never runs the build itself.
metadata:
  author: Saizul Amin
  version: "0.1.0"
---

# React performance review

Measure first, change one thing, measure again. Most wins in a Next.js app come from
shipping less client JavaScript and fixing a handful of expensive re-renders, not from
sprinkling `useMemo` everywhere.

Paths below are relative to this skill's folder (in Claude Code: `${CLAUDE_SKILL_DIR}`).

## When to use

- "This page is slow / janky", "typing in the input lags", "the list re-renders on every keystroke"
- Low Lighthouse/PageSpeed score, poor LCP, INP or CLS in Search Console or RUM data
- "Our bundle is huge", "First Load JS is 400 kB", a dependency suspected of bloat
- "Should I wrap this in useMemo/useCallback/React.memo?", "should we enable the React Compiler?"

## When not to use

- Slow server responses or database queries (profile the backend; check caching in
  `nextjs-app-router-patterns`)
- Infrastructure: CDN, compression, HTTP caching headers (see `nextjs-deploy-selfhost`)
- React Native performance

## Workflow

1. **Classify the problem.** Load time (LCP, JS size, images, fonts) or interaction
   (INP, re-renders, long tasks) or layout shift (CLS). Ask for the slow URL, device class
   and any field data. Never optimise without a symptom.
2. **Measure bundle size.** Pick the input that matches the project:
   ```bash
   # Next.js 13-15: save the build output (route table has Size / First Load JS)
   npx next build | tee build.log
   python3 scripts/bundle_report.py --build-log build.log

   # Any version, including Next.js 16 (build output no longer shows sizes)
   python3 scripts/bundle_report.py --next-dir .next --warn-kb 170

   # webpack stats JSON (`next build --webpack` with webpack-bundle-analyzer's
   # BundleAnalyzerPlugin({ generateStatsFile: true }) in next.config webpack()):
   # heavy and duplicated packages
   python3 scripts/bundle_report.py --stats .next/stats.json --json
   ```
   Rules: PERF001 route over budget, PERF002 large shared JS, PERF003 big asset, PERF004
   heavy package, PERF005 duplicated package, PERF006 big chunk. For an interactive view on
   Next.js 16.1+ use `npx next analyze` (Turbopack) and inspect the import chain of the
   largest modules.
3. **Measure runtime.** Ask the user to record with React DevTools Profiler ("Highlight
   updates" + "Record why each component rendered") and Chrome Performance panel with 4x CPU
   throttling, or run `next build --profile` for a profiling-enabled production build. Read
   the flame chart for components that render often and take long.
4. **Find the cause** with [references/rerender-guide.md](references/rerender-guide.md):
   new object/array/function props each render, context value recreated, state stored too
   high, derived state in effects, unkeyed or index-keyed lists, expensive work in render.
5. **Pick the fix** from [references/bundle-and-assets.md](references/bundle-and-assets.md):
   move code to Server Components, `next/dynamic` for below-the-fold or on-interaction UI,
   lighter libraries, `optimizePackageImports`, image `sizes`/`preload`, `next/font`,
   `next/script` strategies, virtualise long lists, `useDeferredValue`/`useTransition`.
6. **Apply one change at a time**, show the diff, and re-measure with the same method. Report
   before/after numbers. Do not add memoisation that the profiler does not justify; if the
   project enables the React Compiler (`reactCompiler: true`), remove manual memo only where
   the compiler output covers it.

## Output

```
Performance review: /dashboard (mobile, 4x CPU)
Measured
- First load JS: 412 kB gzip (budget 170 kB)   [bundle_report.py --next-dir]
- INP on "filter" input: ~380 ms; <ProductList> renders 1,200 rows on each keystroke
Causes
1. chart.js (200 kB) imported in the page, used only in a collapsed panel
2. ProductList gets a new `filters` object every render; rows are not virtualised
Fixes (in order of impact)
1. const Chart = dynamic(() => import('./Chart'), { ssr: false, loading: ... })  (-190 kB)
2. useDeferredValue(query) + react-window for the list
After: 205 kB, INP ~90 ms
```

## Budgets (defaults used by the script)

| Metric | Good | Investigate |
| --- | --- | --- |
| First-load JS per route (gzip) | < 170 kB | > 300 kB is high |
| Single chunk (gzip) | < 100 kB | > 200 kB is high |
| LCP | < 2.5 s | > 4 s |
| INP | < 200 ms | > 500 ms |
| CLS | < 0.1 | > 0.25 |
