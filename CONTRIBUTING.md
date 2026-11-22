# Contributing to nextjs-react-skills

Thank you for helping! New checks, new skills, false-positive fixes, fixture files from
real-world code (reduced to a minimal example) and clearer docs are all welcome.

- [Ways to contribute](#ways-to-contribute)
- [Good first issues](#good-first-issues)
- [Development setup](#development-setup)
- [Repository layout](#repository-layout)
- [Write a new skill](#write-a-new-skill)
- [Quality bar](#quality-bar)
- [Pull request process](#pull-request-process)

## Ways to contribute

| Size | Idea |
| --- | --- |
| 10 minutes | Fix a typo, clarify a workflow step, add a FAQ entry |
| 30 minutes | Add a missing test case or a fixture that triggers a false positive |
| 1-2 hours | Add a check to an existing script (see below) |
| Half a day | Write a new skill from the template |

Comment on an issue before you start so nobody else picks the same one.

## Good first issues

Each of these is self-contained and touches one script and its test file.

1. **nextjs-app-router-patterns: `searchParams` in layouts.** Report `medium` when a
   `layout.tsx` reads `searchParams` (layouts do not receive them and do not re-render on
   query changes). Add a fixture.
2. **nextjs-app-router-patterns: `export const dynamic` with Cache Components.** When
   `next.config` has `cacheComponents: true`, report `low` for route segment config such as
   `export const dynamic = 'force-static'` and suggest `'use cache'`.
3. **nextjs-seo-metadata: hreflang reciprocity.** In `html` mode, collect
   `<link rel="alternate" hreflang>` per page and report pages whose alternates do not link back.
4. **nextjs-seo-metadata: sitemap vs pages.** Parse a built `sitemap.xml` (`--sitemap FILE`)
   and report prerendered pages missing from it and sitemap URLs with no page.
5. **server-actions-security: mass assignment.** Report `medium` when an action passes
   `Object.fromEntries(formData)` or a spread of request JSON straight into a `data:` object.
6. **server-actions-security: SSRF hint.** Report `medium` when an action or route handler
   calls `fetch()` with a URL taken from `formData`, `searchParams` or request JSON.
7. **react-accessibility-review: heading order.** Per file, report `low` when headings skip
   a level (`<h2>` followed by `<h4>`).
8. **react-accessibility-review: `target="_blank"`.** Report `info` for links opening a new
   tab without visible or screen-reader text saying so.
9. **react-performance-review: `next analyze export` input.** Accept the JSON Lines output of
   `next analyze export` (`--analyze-jsonl FILE`) and report the largest modules per route.
10. **nextjs-env-config: `.env.example` with values.** Report `medium` when `.env.example`
    contains values that look like real credentials (same patterns as ENV002, names only).
11. **react-testing: coverage summary input.** Read `coverage/coverage-summary.json` and list
    components under a line-coverage threshold (`--min-lines 60`).
12. **nextjs-deploy-selfhost: compose checks.** Parse `compose.yaml` (JSON from
    `docker compose config --format json`) and report the app port published on `0.0.0.0`
    and a missing healthcheck.
13. **New skill: `nextjs-i18n-routing`** (see the roadmap in the README).

## Development setup

```bash
git clone https://github.com/saizul/nextjs-react-skills.git
cd nextjs-react-skills
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt

python tools/validate_skills.py   # SKILL.md frontmatter, sections, links, marketplace listing
ruff check . && ruff format --check .
pytest
```

To try your changes in Claude Code, either copy a skill to `~/.claude/skills/` or add your
checkout as a local marketplace:

```bash
claude plugin marketplace add ./nextjs-react-skills
claude plugin install nextjs-react-skills@nextjs-react-skills
```

For Codex, copy the skill folder to `~/.agents/skills/`.

## Repository layout

```
.claude-plugin/
  marketplace.json      marketplace + plugin entry listing every skill
  plugin.json           plugin manifest (name, version, author)
skills/<name>/
  SKILL.md              frontmatter + workflow (the part agents read)
  scripts/*.py          standalone helpers, Python 3.8+ stdlib only
  references/*.md       detail loaded on demand
templates/skill/        copy this to start a new skill
tests/
  test_<skill>.py       one test module per skill
  fixtures/<skill>/     small fake projects (bad/ triggers rules, good/ is clean)
tools/validate_skills.py
```

## Write a new skill

1. Open a "New skill proposal" issue first so we can agree on scope.
2. Copy the template:
   ```bash
   cp -r templates/skill skills/my-new-skill
   mv skills/my-new-skill/scripts/your_script.py skills/my-new-skill/scripts/my_check.py
   ```
3. Edit `SKILL.md`:
   - `name` equals the folder name: lowercase letters, digits, single hyphens, max 64 chars.
   - `description` (max 1024 chars) says **what** it does with concrete keywords and **when**
     to use it, starting the second part with "Use when ...". This text decides whether
     the agent picks the skill, so list the phrases users actually type.
   - Required sections: `## When to use`, `## When not to use`, `## Workflow`, `## Output`.
   - Workflow steps are imperative and numbered, with exact commands, decision points and
     the point where the agent must ask before changing anything.
   - Keep it under 400 lines; move tables, runbooks and long configs to `references/`.
4. Write the script: `argparse` with a useful `--help`, `--json` and `--fail-on`, exit codes
   0 (ok) / 1 (findings) / 2 (error), read-only, offline, never printing secret values. Copy
   the shared helper block from an existing script (comment stripping, file walking, output)
   instead of inventing a new output format.
5. Add `tests/test_my_new_skill.py` and fixtures in `tests/fixtures/my-new-skill/`. Cover
   a `bad/` project that triggers every rule, a `good/` project with no findings, false-positive
   cases (comments, strings, TypeScript generics) and the CLI exit codes.
6. Add the skill to `.claude-plugin/marketplace.json` (`plugins[0].skills`), the README
   skills table, the table in `AGENTS.md` and `CHANGELOG.md` under "Unreleased".
7. Run the validator, ruff and pytest.

## Quality bar

- **Safety first.** Skills show diffs before editing and leave installs, deploys and
  credential rotation to the user. Scripts never print secrets.
- **Deterministic where it matters.** If a step is "find every X in the codebase", write a
  script and test it rather than relying on the model reading hundreds of files.
- **Current.** Target the latest stable Next.js and React, and say which version a rule
  applies to (for example "since Next.js 15"). Link the official docs in references.
- **Low false positives.** If a check is often wrong, make it `info` or drop it, and document
  known false positives in the skill. Prefer missing an edge case to crying wolf.
- **Realistic fixtures.** Reduce real code to the smallest example; use `example.com` and fake
  values that do not look like real keys (secret scanners run in CI).

## Pull request process

1. Fork, create a branch, make focused commits.
2. Make sure CI passes locally (validator, ruff, pytest).
3. Fill in the pull request template.
4. A maintainer reviews within a few days. Small, focused pull requests are merged fastest.

By contributing you agree that your contributions are licensed under the MIT License.
