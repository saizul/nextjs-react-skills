# nextjs-react-skills

[![CI](https://github.com/saizul/nextjs-react-skills/actions/workflows/ci.yml/badge.svg)](https://github.com/saizul/nextjs-react-skills/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/saizul/nextjs-react-skills?sort=semver)](https://github.com/saizul/nextjs-react-skills/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Stars](https://img.shields.io/github/stars/saizul/nextjs-react-skills?style=social)](https://github.com/saizul/nextjs-react-skills/stargazers)

**Agent Skills that make Claude Code and Codex write Next.js App Router and React code the way a senior reviewer would: right server/client split, secure Server Actions, real SEO, fast, accessible and tested.**

Eight skills for the questions that come up in every Next.js project. Each one is a
step-by-step workflow plus a tested, standard-library-only Python scanner, so the agent
checks your actual code instead of guessing, then proposes diffs you approve.

- **Next.js 16 aware.** Async `params`/`cookies()`, `proxy.ts`, Cache Components
  (`'use cache'`, `cacheLife`, `updateTag`), two-argument `revalidateTag`, `default.tsx` for
  parallel routes, `next/image` `preload`, build output without sizes. Works on 14 and 15 too.
- **Read-only by default.** Scanners only read files, never run builds, never touch the
  network and never print env values. Edits are shown as diffs first.
- **Tested.** 135+ pytest tests with fixture projects, CI on Python 3.11-3.13.
- **No dependencies.** Python 3.8+ standard library. No `npm install` needed to run a scan.

## Skills

| Skill | What it does | Try asking |
| --- | --- | --- |
| [nextjs-app-router-patterns](skills/nextjs-app-router-patterns/SKILL.md) | Server vs Client Components, layouts, data fetching, caching and revalidation decisions; scanner for boundary mistakes and Next.js 15/16 breakers (sync params, `cookies()`, slots without `default.tsx`, one-arg `revalidateTag`, `middleware.ts`) | "Should this be a server or client component, and how do I cache this data?" |
| [nextjs-seo-metadata](skills/nextjs-seo-metadata/SKILL.md) | `generateMetadata`, `metadataBase`, `sitemap.ts`, `robots.ts`, OG images, JSON-LD; audits built HTML (`out/`, `.next/server/app`) or `app/` source for missing/duplicate titles, relative canonicals, broken JSON-LD, robots blocking the site | "Why do all my blog posts share one title and no preview image?" |
| [server-actions-security](skills/server-actions-security/SKILL.md) | Auth, zod validation, authorization, CSRF/Origin, open redirects, rate limits; scanner lists every Server Action and mutating route handler and flags what is missing | "Is this server action secure?" |
| [react-performance-review](skills/react-performance-review/SKILL.md) | Re-render causes, when memo helps, React Compiler, code splitting, images/fonts/scripts, Core Web Vitals; report from `next build` output, webpack stats or a `.next` dir with per-route budgets | "Our dashboard loads 400 kB of JS and typing lags" |
| [nextjs-env-config](skills/nextjs-env-config/SKILL.md) | `NEXT_PUBLIC_` exposure audit, server vars in client code, `.env` load order and `.gitignore`, `.env.example` drift, Docker build args, zod-typed env | "Is it safe to put my OpenAI key in NEXT_PUBLIC_?" |
| [react-accessibility-review](skills/react-accessibility-review/SKILL.md) | Static JSX scan (alt text, div onClick, icon-only buttons, labels, tabIndex, aria-hidden, lang) plus fix patterns and axe/Playwright checks | "Make this modal and form accessible" |
| [react-testing](skills/react-testing/SKILL.md) | Vitest/Jest + Testing Library setup and recipes (user-event, MSW, mocking `next/navigation`, Server Actions, hooks); finds untested components and test smells | "Add tests for CheckoutForm and set up Vitest" |
| [nextjs-deploy-selfhost](skills/nextjs-deploy-selfhost/SKILL.md) | `output: 'standalone'`, multi-stage Dockerfile, `.dockerignore`, nginx (headers, streaming, caching), systemd, multi-instance cache/keys; checker for all of them | "Deploy this to my VPS with Docker and nginx" |

## Install

### Claude Code: plugin marketplace (recommended)

```text
/plugin marketplace add saizul/nextjs-react-skills
/plugin install nextjs-react-skills@nextjs-react-skills
```

Or from your shell:

```bash
claude plugin marketplace add saizul/nextjs-react-skills
claude plugin install nextjs-react-skills@nextjs-react-skills
```

Plugin skills are namespaced, e.g. `/nextjs-react-skills:server-actions-security`. Claude
also picks them up automatically when your request matches a skill's description. Update
later with `/plugin marketplace update nextjs-react-skills`.

### Claude Code: copy the skills

```bash
git clone https://github.com/saizul/nextjs-react-skills.git
# all projects (personal skills)
mkdir -p ~/.claude/skills && cp -r nextjs-react-skills/skills/* ~/.claude/skills/
# or just one project (commit it so your team gets it too)
mkdir -p .claude/skills && cp -r nextjs-react-skills/skills/server-actions-security .claude/skills/
```

Each release also has one zip per skill and an all-skills zip under
[Releases](https://github.com/saizul/nextjs-react-skills/releases).

### Codex CLI

Codex reads skills from `~/.agents/skills` (all repositories) and `.agents/skills` in a
repository (from the current directory up to the repository root):

```bash
git clone https://github.com/saizul/nextjs-react-skills.git
mkdir -p ~/.agents/skills && cp -r nextjs-react-skills/skills/* ~/.agents/skills/
# or per repository
mkdir -p .agents/skills && cp -r nextjs-react-skills/skills/nextjs-seo-metadata .agents/skills/
```

Codex also ships a `$skill-installer` skill that can install skills from a GitHub
repository; ask it to install from `saizul/nextjs-react-skills`. Skill locations and the
installer are described in the [Codex skills documentation](https://developers.openai.com/codex/skills);
check it if your Codex version behaves differently. [AGENTS.md](AGENTS.md) explains how
Codex and other agents should use these skills.

### Any other agent

The skills follow the open [Agent Skills format](https://agentskills.io/specification): a
folder with `SKILL.md` (YAML frontmatter + instructions), `scripts/` and `references/`.
Point your agent at the folder, or run the scripts yourself; every script has `--help`.

## Usage examples

```text
> We're upgrading to Next.js 16. What breaks?
  (Runs rsc_boundary_check.py: 14 sync params reads, 2 parallel slots without default.tsx,
   middleware.ts, 3 one-argument revalidateTag calls; proposes diffs file by file.)

> Review the server actions in app/(dashboard) before we launch.
  (action_scan.py finds deleteProject with no auth and updateMember without validation;
   rewrites them with verifySession() + zod + ownership-scoped queries.)

> Our Lighthouse SEO and accessibility scores are bad.
  (seo_audit.py html .next/server/app + a11y_scan.py: no metadataBase, duplicate titles,
   icon-only buttons, inputs without labels; fixes in order of impact.)
```

Run the scripts directly too:

```bash
python3 skills/nextjs-app-router-patterns/scripts/rsc_boundary_check.py .
python3 skills/nextjs-seo-metadata/scripts/seo_audit.py source .
python3 skills/server-actions-security/scripts/action_scan.py . --json
python3 skills/react-performance-review/scripts/bundle_report.py --next-dir .next
python3 skills/nextjs-env-config/scripts/env_audit.py .
python3 skills/react-accessibility-review/scripts/a11y_scan.py components/
python3 skills/react-testing/scripts/find_test_gaps.py . --top 10
python3 skills/nextjs-deploy-selfhost/scripts/selfhost_check.py . --instances 2
```

Every scanner supports `--json` and `--fail-on {info,low,medium,high}`, so you can use them
as CI gates (exit 1 on findings, 2 on usage errors).

## How skills work

At startup the agent loads only each skill's `name` and `description` (about 100 tokens
each). When your request matches a description, it reads that skill's `SKILL.md`: the
workflow, decision points and rules. Longer material lives in `references/` and is read
only when a step needs it. Scripts run as normal commands, so their output is exact and
repeatable.

```
skills/<skill-name>/
  SKILL.md          frontmatter (name, description) + workflow
  scripts/          standalone Python 3 scanner (stdlib only, --help, --json, --fail-on)
  references/       decision guides, recipes, checklists
```

## FAQ

**Will the agent change my code on its own?**
The skills instruct it to show diffs and wait for approval, and to let you run installs and
deploys. The scanners never write files. Your agent's own permission settings still apply.

**Does anything leave my machine?**
No. The scripts make no network requests and send no telemetry. The env audit reports
variable names, never values.

**How accurate are the scanners?**
They are heuristic (regular expressions over comment-stripped source, not a TypeScript
compiler), tuned for low false positives and tested against fixture projects. The
SKILL.md workflows tell the agent to confirm findings by reading the code. False positives
are bugs: please report them with a minimal file.

**Pages Router?**
The env, accessibility, testing, performance and deployment skills apply to both routers.
The App Router, SEO and Server Actions skills target `app/`.

**Do I need Next.js 16?**
No. Advice notes version differences (14, 15, 16). Rules such as async `params` only apply
from 15; the skill checks your `package.json` first.

## Roadmap

Ideas for new skills (great first contributions; see [CONTRIBUTING.md](CONTRIBUTING.md)):

- `nextjs-i18n-routing` - `[lang]` segments, `proxy.ts` locale detection, hreflang, dictionaries
- `nextjs-auth-setup` - Auth.js / Better Auth / Clerk wiring with a DAL and protected routes
- `react-forms` - `useActionState`, `useFormStatus`, optimistic UI, progressive enhancement
- `nextjs-pages-to-app-migration` - incremental migration plan with a route inventory script
- `react-state-management` - when to use context, Zustand, TanStack Query, URL state
- `nextjs-image-optimization` - `next/image` audit (sizes, preload, remotePatterns, formats)
- `tailwind-design-tokens` - Tailwind v4 theme review and unused class scan
- `nextjs-observability` - `instrumentation.ts`, OpenTelemetry, error tracking, Web Vitals RUM

## Contributing

Contributions are welcome: new checks, new skills, false-positive fixes and better docs.
Read [CONTRIBUTING.md](CONTRIBUTING.md) for the skill template, the quality bar and how to
run the validator and tests:

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
python tools/validate_skills.py && ruff check . && ruff format --check . && pytest
```

Please follow the [Code of Conduct](CODE_OF_CONDUCT.md) and report security issues
privately as described in [SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE) (c) Saizul Amin
