#!/usr/bin/env python3
"""Check a Next.js App Router project for server/client component boundary mistakes.

Static, read-only scan of app/ (or src/app/) and the rest of the source tree:
  * route files (page, layout, template, ...) that use hooks or event handlers without "use client"
  * error.tsx / global-error.tsx without "use client" (required)
  * "use client" files that export metadata/generateMetadata, are async, or import server-only modules
  * "use client" on a root or route layout (whole subtree becomes client-rendered)
  * synchronous params / searchParams / cookies() / headers() access (async since Next.js 15,
    removed in 16)
  * revalidateTag() with a single argument (deprecated in Next.js 16)
  * parallel route slots (@slot) without default.tsx (build error in Next.js 16)
  * middleware.ts (deprecated in Next.js 16; rename to proxy.ts)

Heuristic: regexes over comment-stripped source, not a full parser. Review each finding.
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

ROUTE_FILES = {"page", "layout", "template", "loading", "not-found", "default", "forbidden", "unauthorized"}
PARAM_FILES = {"page", "layout", "default", "template", "route", "opengraph-image", "twitter-image", "icon"}
CLIENT_HOOKS = re.compile(
    r"\buse(State|Effect|LayoutEffect|InsertionEffect|Reducer|Ref|Context|Transition|DeferredValue|"
    r"Optimistic|ActionState|SyncExternalStore|EffectEvent|FormStatus|Router|Pathname|SearchParams|"
    r"SelectedLayoutSegments?|Params)\s*[(<]"
)
EVENT_PROP = re.compile(r"\son[A-Z][A-Za-z]+=\{")
BROWSER_GLOBALS = re.compile(r"\b(window|document|localStorage|sessionStorage|navigator)\.\w")
SERVER_ONLY_IMPORTS = re.compile(
    r"""(?:from\s+|import\s+|require\()\s*['"](server-only|next/headers|fs|fs/promises|node:[a-z_/]+|"""
    r"""child_process|@prisma/client|pg|mysql2(?:/promise)?|mongoose|bcrypt|better-sqlite3|"""
    r"""drizzle-orm/[a-z0-9-]+|@aws-sdk/[a-z0-9-]+)['"]"""
)
CLIENT_SERVER_API = re.compile(
    r"""import\s*\{[^}]*\b(revalidatePath|revalidateTag|updateTag|unstable_cache|cookies|headers)\b[^}]*\}\s*"""
    r"""from\s*['"]next/(cache|headers)['"]"""
)


def find_app_dir(root: Path) -> Path | None:
    for cand in (root / "app", root / "src" / "app"):
        if cand.is_dir():
            return cand
    return None


def check_file(path: Path, root: Path, app_dir: Path | None, strict: bool) -> list[dict]:
    src = read_text(path)
    code = strip_comments(src)
    rp = rel(path, root)
    stem = path.name.split(".")[0]
    kind = directive(code)
    in_app = app_dir is not None and app_dir in path.parents
    out: list[dict] = []

    def add(sev, rule, idx, msg, fix=""):
        out.append(finding(sev, rule, rp, line_of(code, idx) if idx is not None else 0, msg, fix))

    client_signal = CLIENT_HOOKS.search(code) or EVENT_PROP.search(code)
    if in_app and stem in ("error", "global-error") and kind != "client":
        add(
            "high",
            "RSC002",
            0,
            f"{path.name} must be a Client Component",
            "add 'use client' as the first line",
        )
    elif kind is None and client_signal and path.suffix in (".tsx", ".jsx", ".js"):
        if in_app and stem in ROUTE_FILES:
            add(
                "high",
                "RSC001",
                client_signal.start(),
                f"route file uses client-only feature '{client_signal.group(0).strip()}' without 'use client'",
                "move the interactive part into a small 'use client' component and import it here",
            )
        elif strict:
            add(
                "info",
                "RSC010",
                client_signal.start(),
                "uses hooks/event handlers without 'use client'; fine only if every importer is a Client Component",
                "add 'use client' if this module is imported from a Server Component",
            )

    if kind == "client":
        m = re.search(r"export\s+(const\s+metadata\b|(async\s+)?function\s+generateMetadata\b)", code)
        if m:
            add(
                "high",
                "RSC004",
                m.start(),
                "metadata exports are ignored in Client Components",
                "keep page/layout as a Server Component and move interactivity into a child",
            )
        m = re.search(r"export\s+default\s+async\s+function|export\s+default\s+async\s*\(", code)
        if m:
            add(
                "high",
                "RSC006",
                m.start(),
                "async Client Component (only Server Components can be async)",
                "fetch on the server and pass data as props, or use use()/a data library in the client",
            )
        for m in SERVER_ONLY_IMPORTS.finditer(code):
            add(
                "high",
                "RSC005",
                m.start(),
                f"Client Component imports server-only module '{m.group(1)}'",
                "move this code to a Server Component, Server Action or route handler",
            )
        for m in CLIENT_SERVER_API.finditer(code):
            add(
                "high",
                "RSC005",
                m.start(),
                f"Client Component imports '{m.group(1)}' from next/{m.group(2)} (server-only API)",
                "call it inside a Server Action ('use server') instead",
            )
        if in_app and stem == "layout":
            add(
                "medium",
                "RSC003",
                0,
                "'use client' on a layout makes every page below it client-rendered",
                "keep the layout on the server; wrap only providers/interactive widgets in client files",
            )
        elif in_app and stem == "page":
            add(
                "low",
                "RSC003",
                0,
                "'use client' on a page: no server data fetching or metadata for this route",
                "render a server page that fetches data and passes it to a client child",
            )
        m = re.search(r"useEffect\s*\(\s*(async\s*)?\(\s*\)\s*=>\s*\{[^}]*\bfetch\s*\(", code, re.S)
        if m and in_app:
            add(
                "low",
                "RSC009",
                m.start(),
                "initial data fetched in useEffect (waterfall, no SSR)",
                "fetch in the parent Server Component and pass the result as props",
            )

    if kind != "client" and in_app and stem in PARAM_FILES:
        for name in ("params", "searchParams"):
            if re.search(rf"\b{name}\b", code) and not re.search(
                rf"await\s+(props\.)?{name}\b|use\(\s*(props\.)?{name}\s*\)|\.then\(", code
            ):
                m = re.search(rf"\b{name}\??\.\w+|\{{[^}}]*\}}\s*=\s*(props\.)?{name}\b", code)
                if m:
                    add(
                        "high",
                        "RSC008",
                        m.start(),
                        f"synchronous {name} access ({name} is a Promise since Next.js 15)",
                        f"const {{ ... }} = await {name}  (type it as Promise<...>)",
                    )
    for m in re.finditer(r"\b(cookies|headers|draftMode)\(\)\s*\.", code):
        add(
            "high",
            "RSC008",
            m.start(),
            f"synchronous {m.group(1)}() access (must be awaited since Next.js 15)",
            f"(await {m.group(1)}()).get(...)",
        )
    for m in re.finditer(r"\brevalidateTag\(\s*([^,()]+?)\s*\)", code):
        add(
            "medium",
            "RSC011",
            m.start(),
            "revalidateTag() with one argument is deprecated in Next.js 16",
            f"revalidateTag({m.group(1)}, 'max') for stale-while-revalidate, or updateTag() in a "
            "Server Action for read-your-writes",
        )
    return out


def check_project(root: Path, strict: bool = False) -> list[dict]:
    findings: list[dict] = []
    app_dir = find_app_dir(root) if root.is_dir() else None
    for path in iter_files(root):
        findings += check_file(path, root, app_dir, strict)
    if app_dir:
        for dirpath, dirnames, _ in os.walk(app_dir):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for d in dirnames:
                slot = Path(dirpath) / d
                if d.startswith("@") and not any(
                    (slot / f"default{ext}").exists() for ext in (".tsx", ".jsx", ".ts", ".js")
                ):
                    findings.append(
                        finding(
                            "high",
                            "RSC012",
                            rel(slot, root),
                            0,
                            "parallel route slot without default.tsx (build fails in Next.js 16)",
                            "add default.tsx that returns null or calls notFound()",
                        )
                    )
    if root.is_dir():
        for base in (root, root / "src"):
            for ext in SOURCE_EXTS:
                mw = base / f"middleware{ext}"
                if mw.is_file():
                    findings.append(
                        finding(
                            "low",
                            "RSC013",
                            rel(mw, root),
                            0,
                            "middleware.ts is deprecated in Next.js 16",
                            "rename to proxy.ts and the exported function to proxy "
                            "(npx @next/codemod@canary middleware-to-proxy .)",
                        )
                    )
    return findings


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Find server/client component boundary mistakes in a Next.js App Router project."
    )
    p.add_argument("path", nargs="?", default=".", help="project root or a single file (default: .)")
    p.add_argument("--json", action="store_true", help="print JSON")
    p.add_argument("--fail-on", choices=SEVERITIES, default="medium", help="exit 1 at this severity")
    p.add_argument("--strict", action="store_true", help="also report non-route files using hooks without 'use client'")
    args = p.parse_args(argv)
    root = Path(args.path)
    if not root.exists():
        print(f"error: {root} does not exist", file=sys.stderr)
        return 2
    return emit(check_project(root, args.strict), args, "rsc boundary check")


if __name__ == "__main__":
    sys.exit(main())
