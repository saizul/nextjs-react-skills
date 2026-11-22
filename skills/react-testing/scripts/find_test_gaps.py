#!/usr/bin/env python3
"""Find untested React components/hooks and test-suite problems in a JS/TS project.

  * detects the runner and Testing Library setup from package.json and config files
    (vitest/jest, jsdom/happy-dom environment, @testing-library/react, user-event, jest-dom, msw)
  * lists components and hooks with no matching *.test.* / *.spec.* / __tests__ file,
    ranked by size and interactivity (hooks, event handlers)
  * flags test smells: .only (fails CI silently), skipped tests, real timers/sleeps,
    container.querySelector, fireEvent where user-event is installed, snapshot-only files,
    heavy getByTestId use

Next.js route files (page, layout, route, ...) are skipped by default: async Server Components
are better covered by end-to-end tests (Playwright). Read-only.
Exit codes: 0 = nothing at or above --fail-on, 1 = findings, 2 = usage error.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

# ---- shared helpers (identical copy in every script of this repo; keep in sync) ----
SOURCE_EXTS = (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs")
SKIP_DIRS = {
    "node_modules",
    ".next",
    ".git",
    "dist",
    "build",
    "out",
    "coverage",
    ".turbo",
    ".vercel",
    ".output",
    "storybook-static",
    "__pycache__",
}
SEVERITIES = ["info", "low", "medium", "high"]


def iter_files(root: Path, exts=SOURCE_EXTS):
    """Yield source files under root, skipping build output and dependencies."""
    if root.is_file():
        yield root
        return
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            if name.endswith(exts) and not name.endswith(".d.ts"):
                yield Path(dirpath) / name


def strip_comments(src: str) -> str:
    """Blank out // and /* */ comments, keeping strings, offsets and line numbers."""
    out = []
    i, n, quote = 0, len(src), None
    while i < n:
        c = src[i]
        if quote:
            if c == "\\" and i + 1 < n:
                out.append(src[i : i + 2])
                i += 2
                continue
            if c == quote or (c == "\n" and quote != "`"):
                quote = None
            out.append(c)
            i += 1
            continue
        if c == "/" and src.startswith("//", i):
            j = src.find("\n", i)
            j = n if j == -1 else j
            out.append(" " * (j - i))
            i = j
            continue
        if c == "/" and src.startswith("/*", i):
            j = src.find("*/", i + 2)
            j = n if j == -1 else j + 2
            out.append(re.sub(r"[^\n]", " ", src[i:j]))
            i = j
            continue
        if c == "\\" and i + 1 < n:
            out.append(src[i : i + 2])
            i += 2
            continue
        if c in "'\"`":
            quote = c
        out.append(c)
        i += 1
    return "".join(out)


def directive(code: str) -> str | None:
    """Return 'client' or 'server' when the file starts with that directive."""
    m = re.match(r"\s*(?:(['\"])use strict\1;?\s*)?(['\"])use (client|server)\2", code)
    return m.group(3) if m else None


def line_of(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root if root.is_dir() else root.parent).as_posix()
    except ValueError:
        return path.as_posix()


def emit(findings, args, header: str) -> int:
    """Print findings (text or JSON) and return the exit code for --fail-on."""
    findings = sorted(findings, key=lambda f: (-SEVERITIES.index(f["severity"]), f["file"], f["line"]))
    counts = {s: sum(1 for f in findings if f["severity"] == s) for s in reversed(SEVERITIES)}
    if args.json:
        print(json.dumps({"summary": counts, "findings": findings}, indent=2))
    else:
        print(f"{header}: " + ", ".join(f"{v} {k}" for k, v in counts.items()))
        for f in findings:
            loc = f"{f['file']}:{f['line']}" if f["line"] else f["file"]
            print(f"{f['severity'].upper():6} {f['rule']}  {loc}\n       {f['message']}")
            if f.get("fix"):
                print(f"       fix: {f['fix']}")
    threshold = SEVERITIES.index(args.fail_on)
    return 1 if any(SEVERITIES.index(f["severity"]) >= threshold for f in findings) else 0


def finding(severity, rule, file, line, message, fix=""):
    return {"severity": severity, "rule": rule, "file": file, "line": line, "message": message, "fix": fix}


# ---- end shared helpers ----

TEST_RE = re.compile(r"\.(test|spec)\.[cm]?[jt]sx?$")
ROUTE_STEMS = {
    "page",
    "layout",
    "template",
    "loading",
    "error",
    "global-error",
    "not-found",
    "default",
    "route",
    "proxy",
    "middleware",
    "instrumentation",
    "sitemap",
    "robots",
    "manifest",
    "opengraph-image",
    "twitter-image",
    "icon",
    "apple-icon",
}
SKIP_NAME = re.compile(
    r"\.(stories|story|config|d|mock)\.|^(types?|constants?)\.|^(setup-?tests?|test-?setup|vitest\.setup|jest\.setup)\.",
    re.I,
)
SOURCE_DIRS = ("src", "app", "components", "hooks", "lib", "features", "ui")


def load_package(root: Path) -> dict:
    path = root / "package.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(read_text(path))
    except json.JSONDecodeError:
        return {}


def detect_setup(root: Path) -> tuple[dict, list[dict]]:
    pkg = load_package(root)
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    setup = {
        "runner": "vitest" if "vitest" in deps else "jest" if "jest" in deps else None,
        "react_testing_library": "@testing-library/react" in deps,
        "user_event": "@testing-library/user-event" in deps,
        "jest_dom": "@testing-library/jest-dom" in deps,
        "msw": "msw" in deps,
        "playwright": "@playwright/test" in deps,
        "dom_env": "jsdom" in deps or "happy-dom" in deps or "jest-environment-jsdom" in deps,
    }
    out: list[dict] = []
    configs = [p for p in root.iterdir() if re.match(r"^(vitest|jest)\.config\.", p.name)] if root.is_dir() else []
    cfg_text = "\n".join(read_text(p) for p in configs)
    if setup["runner"] is None:
        out.append(
            finding(
                "medium",
                "TST001",
                "package.json",
                0,
                "no test runner (vitest or jest) in package.json",
                "npm i -D vitest @vitejs/plugin-react jsdom @testing-library/react @testing-library/dom "
                "@testing-library/user-event @testing-library/jest-dom vite-tsconfig-paths",
            )
        )
        return setup, out
    if not setup["react_testing_library"]:
        out.append(finding("medium", "TST002", "package.json", 0, "@testing-library/react is not installed"))
    if not setup["dom_env"]:
        out.append(
            finding(
                "medium",
                "TST003",
                "package.json",
                0,
                "no DOM environment (jsdom / happy-dom) installed",
                "npm i -D jsdom and set test.environment = 'jsdom'",
            )
        )
    if configs and setup["runner"] == "vitest" and not re.search(r"environment\s*:\s*['\"](jsdom|happy-dom)", cfg_text):
        out.append(
            finding(
                "medium",
                "TST003",
                configs[0].name,
                0,
                "vitest config does not set a DOM environment",
                "test: { environment: 'jsdom' }",
            )
        )
    if not setup["user_event"]:
        out.append(
            finding(
                "low",
                "TST004",
                "package.json",
                0,
                "@testing-library/user-event not installed",
                "user-event simulates real interactions (focus, keyboard) better than fireEvent",
            )
        )
    if not setup["jest_dom"]:
        out.append(
            finding(
                "low",
                "TST005",
                "package.json",
                0,
                "@testing-library/jest-dom not installed",
                "adds toBeInTheDocument(), toHaveAccessibleName() ... ; import it in the setup file",
            )
        )
    if setup["runner"] and not configs:
        out.append(finding("info", "TST006", ".", 0, f"{setup['runner']} has no config file in the project root"))
    return setup, out


def source_files(root: Path, include_routes: bool):
    dirs = [root / d for d in SOURCE_DIRS if (root / d).is_dir()] or [root]
    seen = set()
    for d in dirs:
        for path in iter_files(d, (".tsx", ".jsx", ".ts", ".js")):
            if path in seen:
                continue
            seen.add(path)
            if TEST_RE.search(path.name) or "__tests__" in path.parts or "__mocks__" in path.parts:
                continue
            if SKIP_NAME.search(path.name):
                continue
            stem = path.name.split(".")[0]
            if not include_routes and stem in ROUTE_STEMS:
                continue
            yield path


def test_index(root: Path) -> set[str]:
    stems = set()
    for path in iter_files(root, (".tsx", ".jsx", ".ts", ".js", ".mjs", ".cjs")):
        if TEST_RE.search(path.name) or ("__tests__" in path.parts and path.suffix in (".ts", ".tsx", ".js", ".jsx")):
            stem = path.name.split(".")[0].lower()
            if stem == "index":
                parent = path.parent.parent if path.parent.name == "__tests__" else path.parent
                stem = parent.name.lower()
            stems.add(stem)
    return stems


def gaps(root: Path, include_routes: bool) -> list[dict]:
    tested = test_index(root)
    out = []
    for path in source_files(root, include_routes):
        code = strip_comments(read_text(path))
        stem = path.name.split(".")[0]
        if stem == "index":
            stem = path.parent.name
        is_hook = bool(re.match(r"use[A-Z]", stem)) or bool(re.search(r"export\s+(function|const)\s+use[A-Z]", code))
        is_component = path.suffix in (".tsx", ".jsx") and bool(re.search(r"<[A-Za-z]", code))
        if not (is_hook or is_component):
            continue
        if stem.lower() in tested:
            continue
        handlers = len(re.findall(r"\son[A-Z]\w*=\{", code))
        hooks = len(re.findall(r"\buse[A-Z]\w*\s*\(", code))
        lines = code.count("\n") + 1
        score = lines // 20 + handlers * 2 + hooks * 2 + (5 if is_hook else 0)
        out.append(
            {
                "file": rel(path, root),
                "kind": "hook" if is_hook else "component",
                "lines": lines,
                "handlers": handlers,
                "hooks": hooks,
                "score": score,
            }
        )
    return sorted(out, key=lambda g: (-g["score"], g["file"]))


def smells(root: Path, setup: dict) -> list[dict]:
    out = []
    for path in iter_files(root, (".tsx", ".jsx", ".ts", ".js", ".mjs", ".cjs")):
        if not TEST_RE.search(path.name) and "__tests__" not in path.parts:
            continue
        code = strip_comments(read_text(path))
        rp = rel(path, root)

        def add(sev, rule, m, msg, fix="", _rp=rp, _code=code):
            out.append(finding(sev, rule, _rp, line_of(_code, m.start()) if m else 0, msg, fix))

        for m in re.finditer(r"\b(it|test|describe)\.only\s*\(", code):
            add(
                "high",
                "TST010",
                m,
                f"{m.group(1)}.only: every other test in the file is skipped",
                "remove .only; add --allowOnly=false (vitest) or a lint rule in CI",
            )
        skipped = list(re.finditer(r"\b(it|test|describe)\.(skip|todo)\s*\(|\bx(it|describe)\s*\(", code))
        if skipped:
            add("low", "TST011", skipped[0], f"{len(skipped)} skipped/todo test(s)")
        m = re.search(r"new Promise\(\s*\(?\s*\w*\s*\)?\s*=>\s*setTimeout|\bsleep\s*\(\s*\d+", code)
        if m:
            add(
                "medium",
                "TST012",
                m,
                "real-time sleep in a test (slow and flaky)",
                "await findBy*/waitFor, or vi.useFakeTimers() / jest.useFakeTimers()",
            )
        m = re.search(r"container\.querySelector(All)?\s*\(", code)
        if m:
            add(
                "low",
                "TST013",
                m,
                "container.querySelector ties the test to markup",
                "query by role/label: screen.getByRole('button', { name: /save/i })",
            )
        if setup.get("user_event"):
            m = re.search(r"\bfireEvent\.(click|change|input|keyDown|submit)\s*\(", code)
            if m:
                add(
                    "low",
                    "TST014",
                    m,
                    f"fireEvent.{m.group(1)} while user-event is installed",
                    "const user = userEvent.setup(); await user.click(...)",
                )
        snaps = len(re.findall(r"toMatch(Inline)?Snapshot\s*\(", code))
        expects = len(re.findall(r"\bexpect\s*\(", code))
        if snaps and snaps == expects:
            add(
                "low",
                "TST015",
                None,
                "snapshot-only test file (passes after any re-render)",
                "assert behaviour: visible text, roles, callbacks",
            )
        tid = len(re.findall(r"\b(get|query|find)(All)?ByTestId\s*\(", code))
        if tid >= 5:
            add(
                "low",
                "TST016",
                None,
                f"{tid} *ByTestId queries; prefer accessible queries",
                "getByRole / getByLabelText reflect what users and assistive tech see",
            )
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Find untested React components/hooks and test-suite smells.")
    p.add_argument("path", nargs="?", default=".", help="project root (default: .)")
    p.add_argument("--top", type=int, default=20, help="how many untested files to list (default 20)")
    p.add_argument("--include-routes", action="store_true", help="also list Next.js route files")
    p.add_argument("--json", action="store_true", help="print JSON")
    p.add_argument("--fail-on", choices=SEVERITIES, default="high", help="exit 1 at this severity (default high)")
    args = p.parse_args(argv)
    root = Path(args.path)
    if not root.is_dir():
        print(f"error: {root} is not a directory", file=sys.stderr)
        return 2
    setup, findings = detect_setup(root)
    findings += smells(root, setup)
    untested = gaps(root, args.include_routes)
    if args.json:
        threshold = SEVERITIES.index(args.fail_on)
        print(
            json.dumps(
                {
                    "setup": setup,
                    "untested": untested[: args.top],
                    "untested_total": len(untested),
                    "findings": findings,
                },
                indent=2,
            )
        )
        return 1 if any(SEVERITIES.index(f["severity"]) >= threshold for f in findings) else 0
    print("setup: " + ", ".join(f"{k}={v}" for k, v in setup.items()))
    print(f"untested components/hooks: {len(untested)} (top {min(args.top, len(untested))} by risk)")
    for g in untested[: args.top]:
        print(
            f"  {g['score']:>3}  {g['kind']:9} {g['file']}  "
            f"({g['lines']} lines, {g['handlers']} handlers, {g['hooks']} hooks)"
        )
    return emit(findings, args, "test suite")


if __name__ == "__main__":
    sys.exit(main())
