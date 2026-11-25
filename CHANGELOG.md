# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- `nextjs-env-config`: `env_audit.py` reports ENV012 when the same key is assigned twice in one
  `.env*` file (only the last value is used), with the line of each assignment.

## [0.1.0] - 2026-11-22

### Added

- `nextjs-app-router-patterns`: server/client decision guide, data fetching and caching
  (Cache Components, `'use cache'`, `updateTag`, `revalidateTag(tag, profile)`), patterns, and
  `rsc_boundary_check.py` for boundary mistakes and Next.js 15/16 breaking changes.
- `nextjs-seo-metadata`: Metadata API recipes, sitemap/robots/OG image/JSON-LD, checklist, and
  `seo_audit.py` with `html` (built pages) and `source` (app/) modes.
- `server-actions-security`: secure action pattern, threat model, and `action_scan.py` for
  missing auth, validation, rate limits, open redirects, error leaks and unsafe config.
- `react-performance-review`: re-render guide, bundle/image/font/script guide, and
  `bundle_report.py` for `next build` logs, webpack stats and `.next` directories.
- `nextjs-env-config`: env rules (inlining, load order, Docker), and `env_audit.py` that reports
  exposure and drift without printing values.
- `react-accessibility-review`: fix patterns, automated testing guide, and `a11y_scan.py`
  static JSX/TSX scanner.
- `react-testing`: Vitest/Jest setup, Testing Library recipes, and `find_test_gaps.py` for
  untested components/hooks and test smells.
- `nextjs-deploy-selfhost`: Docker/nginx/systemd files, caching and scaling guide, and
  `selfhost_check.py` for next.config, Dockerfile, .dockerignore and nginx.
- Claude Code plugin marketplace manifest, `tools/validate_skills.py`, CI and release workflows.

[Unreleased]: https://github.com/saizul/nextjs-react-skills/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/saizul/nextjs-react-skills/releases/tag/v0.1.0
