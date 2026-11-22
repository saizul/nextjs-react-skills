## What does this pull request do?

<!-- One or two sentences. Link the issue: "Closes #123". -->

## Type

- [ ] New skill
- [ ] New check or option in an existing script
- [ ] Workflow / reference improvement
- [ ] Bug fix
- [ ] Repository tooling (validator, CI)

## Checklist

- [ ] `python tools/validate_skills.py` passes
- [ ] `ruff check . && ruff format --check .` passes
- [ ] `pytest` passes; new script behaviour has tests with fixtures in `tests/fixtures/<skill>/`
- [ ] Scripts use only the Python standard library (or POSIX shell), support `--help`, have a
      `--json` option where output is structured, and exit non-zero on findings
- [ ] Read-only by default; scripts never print env values or secrets; any file edit, install
      or deploy step is shown to the user and needs confirmation in the SKILL.md workflow
- [ ] No real secrets, API keys or credentials in fixtures (use `example.com` and obviously fake
      values that secret scanners do not match)
- [ ] New skills: listed in `.claude-plugin/marketplace.json`, the README skills table, AGENTS.md and CHANGELOG.md
