# AGENTS.md

Guidance for Codex CLI and other coding agents that use or work on this repository.

## Using the skills

The skills live in `skills/<name>/SKILL.md` and follow the Agent Skills format. Codex
discovers them when they are copied to `~/.agents/skills/` or `.agents/skills/` (see
README "Install"). If you are reading this file inside the repository instead:

1. Pick the skill whose `description` matches the user's request:

   | Request is about | Skill |
   | --- | --- |
   | server vs client components, layouts, data fetching, caching, revalidation, Next.js 16 upgrade | `nextjs-app-router-patterns` |
   | metadata, titles, Open Graph, sitemap, robots, canonical, JSON-LD | `nextjs-seo-metadata` |
   | Server Actions, `'use server'`, API route security, form validation, CSRF | `server-actions-security` |
   | slow pages, re-renders, bundle size, Core Web Vitals, memo/useCallback | `react-performance-review` |
   | `.env` files, `NEXT_PUBLIC_`, undefined env vars, leaked keys | `nextjs-env-config` |
   | accessibility, a11y, WCAG, labels, alt text, keyboard, screen readers | `react-accessibility-review` |
   | tests, Vitest, Jest, Testing Library, mocking, flaky tests | `react-testing` |
   | Docker, nginx, VPS, standalone output, self-hosting, multiple instances | `nextjs-deploy-selfhost` |

2. Read that `SKILL.md` completely and follow its Workflow section in order.
3. Paths such as `scripts/x.py` and `references/y.md` are relative to the skill folder.
   `${CLAUDE_SKILL_DIR}` in the text means that folder; Codex does not expand it.
4. Read files in `references/` only when a workflow step points to them.

## Safety rules (apply to every skill)

- Run the read-only scanners freely; they never write files or use the network.
- Show a diff before editing source files, and apply it only after the user agrees.
- Let the user run (or explicitly approve) package installs, builds that take long,
  deploys, service restarts, credential rotation and git history rewrites.
- Never print, log or paste environment variable values, API keys or tokens. The env audit
  prints names only; keep it that way when summarising.
- Treat a secret found in client code or committed files as compromised: tell the user to
  rotate it; renaming the variable is not enough.

## Working on this repository

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
python tools/validate_skills.py   # frontmatter, sections, links, marketplace listing
ruff check . && ruff format --check .
pytest
```

- Scripts: Python 3.8+ standard library only, `#!/usr/bin/env python3`, `argparse` with
  `--help`, `--json`, `--fail-on`, exit 0/1/2 (ok / findings / error). Each script is a single
  file; the shared helper block between `# ---- shared helpers` and `# ---- end shared helpers`
  is identical in every script, so keep copies in sync when you change it.
- Every script needs tests in `tests/test_<skill_with_underscores>.py` with fixture projects
  in `tests/fixtures/<skill>/` (a `bad/` project that triggers each rule and a `good/` project
  that is clean). Use `example.com` and fake values that secret scanners do not match.
  A fixture's own `.gitignore` is stored as `gitignore.fixture` (tests rename it) so git does
  not drop fixture `.env.local` files.
- Keep each `SKILL.md` under 400 lines; move detail to `references/`.
- A new skill must be added to `.claude-plugin/marketplace.json` (`plugins[0].skills`), the
  README table, the table above and `CHANGELOG.md`. The validator enforces the manifest.
