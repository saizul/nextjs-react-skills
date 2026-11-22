# Security Policy

## Supported versions

| Version | Supported |
| --- | --- |
| 0.1.x | yes |

## What counts as a vulnerability

These skills are run by AI agents inside real codebases, so unsafe guidance is treated like a
code vulnerability:

- A script that writes, deletes or uploads files, runs a build or package install, or makes
  a network request (all scripts here are read-only and offline)
- A script that prints a secret value (`.env` values, API keys, tokens), including in `--json`
- A `SKILL.md` workflow that tells the agent to deploy, restart services, rotate credentials
  or rewrite git history without asking the user first
- Security guidance that is wrong in a way that creates a vulnerability (for example
  recommending a Server Action pattern without authorization, or `allowedOrigins: ['*']`)
- Command injection or path traversal: crafted source files, configs or build output that make
  a script execute something or read outside the given directory

A scanner that misses an issue (false negative) is a normal bug: please open an issue.

## Reporting

Please **do not** open a public issue. Use
[GitHub private vulnerability reporting](https://github.com/saizul/nextjs-react-skills/security/advisories/new)
with the affected skill, version, impact and steps to reproduce. Remove secrets and
proprietary code from examples.

You will get an answer within 5 working days. Fixes are released as soon as possible and
credited in the changelog unless you prefer otherwise.
