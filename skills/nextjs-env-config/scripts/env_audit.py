#!/usr/bin/env python3
"""Audit environment variable usage and exposure in a Next.js project.

Reads .env* files (names only; values are never printed), next.config.*, Dockerfile and
.gitignore, and scans the source for process.env usage. Reports:
  * NEXT_PUBLIC_ variables whose name or value looks secret (inlined into browser JS)
  * next.config `env: {...}` keys that copy server variables into the client bundle
  * server-only variables read in "use client" files (undefined in the browser)
  * dynamic process.env[...] access in client files (never inlined)
  * .env files with real values that .gitignore does not cover
  * variables used in code but missing from .env.example, and vice versa
  * NEXT_PUBLIC_ variables a Dockerfile does not pass at build time (ARG)
  * NODE_ENV set in a .env file

Read-only, offline. Exit codes: 0 = nothing at or above --fail-on, 1 = findings, 2 = usage error.
"""

from __future__ import annotations

import argparse
import fnmatch
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

SECRET_NAME = re.compile(
    r"SECRET|PRIVATE|PASSWORD|PASSWD|TOKEN|API_?KEY|ACCESS_?KEY|CREDENTIAL|DATABASE_URL|DB_URL|_DSN_SERVER|WEBHOOK|SIGNING"
)
PUBLIC_OK = re.compile(
    r"PUBLISHABLE|ANON_?KEY|SITE_?KEY|MEASUREMENT_ID|PUBLIC_KEY|CLIENT_ID|MAPS_API_KEY|POSTHOG_KEY|RECAPTCHA_SITE"
)
SECRET_VALUE = re.compile(
    r"^(sk_live_|sk_test_|rk_live_|ghp_|github_pat_|xox[abp]-|AKIA|ASIA|-----BEGIN|eyJhbGciOi|"
    r"postgres(ql)?://[^@\s]+:[^@\s]+@|mysql://[^@\s]+:[^@\s]+@|mongodb(\+srv)?://[^@\s]+:[^@\s]+@|SG\.)"
)
ENV_FILE = re.compile(r"^\.env(\..+)?$")
EXAMPLE_FILE = re.compile(r"^\.env\.(example|sample|template|defaults)$")
NEXT_BUILTIN = {
    "NODE_ENV",
    "NEXT_RUNTIME",
    "NEXT_PHASE",
    "PORT",
    "HOSTNAME",
    "VERCEL",
    "VERCEL_ENV",
    "VERCEL_URL",
    "CI",
}
USE_RE = re.compile(r"process\.env\.([A-Z_][A-Z0-9_]*)|process\.env\[\s*['\"]([A-Z_][A-Z0-9_]*)['\"]\s*\]")
DESTRUCT_RE = re.compile(r"\{([^}]*)\}\s*=\s*process\.env\b")
DYNAMIC_RE = re.compile(r"process\.env\[\s*(?!['\"])")


def parse_env_file(text: str) -> dict[str, str]:
    out = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        line = line[7:].strip() if line.startswith("export ") else line
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        else:
            value = value.split(" #", 1)[0].strip()
        out[key.strip()] = value
    return out


def gitignore_patterns(root: Path) -> list[str]:
    path = root / ".gitignore"
    if not path.is_file():
        return []
    pats = []
    for raw in read_text(path).splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            pats.append(line)
    return pats


def is_ignored(name: str, patterns: list[str]) -> bool:
    ignored = False
    for pat in patterns:
        neg = pat.startswith("!")
        p = pat[1:] if neg else pat
        p = p.lstrip("/").rstrip("/")
        if fnmatch.fnmatch(name, p) or fnmatch.fnmatch(name, p.split("/")[-1]):
            ignored = not neg
    return ignored


def audit(root: Path) -> list[dict]:
    findings: list[dict] = []
    env_files = sorted(p for p in root.iterdir() if p.is_file() and ENV_FILE.match(p.name)) if root.is_dir() else []
    defined: dict[str, set[str]] = {}
    example_keys: set[str] = set()
    has_example = False
    patterns = gitignore_patterns(root)
    for path in env_files:
        values = parse_env_file(read_text(path))
        if EXAMPLE_FILE.match(path.name):
            has_example = True
            example_keys |= set(values)
            continue
        for key in values:
            defined.setdefault(key, set()).add(path.name)
        if any(values.values()) and not is_ignored(path.name, patterns):
            sev = "high" if path.name.endswith(".local") else "medium" if path.name == ".env" else "low"
            findings.append(
                finding(
                    sev,
                    "ENV001",
                    path.name,
                    0,
                    f"{path.name} has values but is not covered by .gitignore"
                    + ("" if sev != "low" else " (fine for non-secret defaults; never put secrets here)"),
                    "add `.env*` and `!.env.example` to .gitignore; rotate anything already committed",
                )
            )
        for key, value in values.items():
            if key.startswith("NEXT_PUBLIC_"):
                if SECRET_VALUE.search(value):
                    findings.append(
                        finding(
                            "high",
                            "ENV002",
                            path.name,
                            0,
                            f"{key} holds what looks like a secret credential; it is inlined into browser JS",
                            "rename without NEXT_PUBLIC_, read it only on the server, rotate the credential",
                        )
                    )
                elif SECRET_NAME.search(key[12:]) and not PUBLIC_OK.search(key):
                    findings.append(
                        finding(
                            "high",
                            "ENV003",
                            path.name,
                            0,
                            f"{key}: secret-looking name with NEXT_PUBLIC_ prefix (shipped to every visitor)",
                            "drop the prefix and move the code that uses it to the server",
                        )
                    )
            if key == "NODE_ENV":
                findings.append(
                    finding(
                        "low",
                        "ENV004",
                        path.name,
                        0,
                        "NODE_ENV set in an env file (Next.js manages it; non-standard values break builds)",
                        "remove it; next dev/build/start set NODE_ENV",
                    )
                )

    used: dict[str, list[tuple[str, int, bool]]] = {}
    for path in iter_files(root):
        code = strip_comments(read_text(path))
        rp = rel(path, root)
        client = directive(code) == "client"
        for m in USE_RE.finditer(code):
            name = m.group(1) or m.group(2)
            used.setdefault(name, []).append((rp, line_of(code, m.start()), client))
        for m in DESTRUCT_RE.finditer(code):
            for part in m.group(1).split(","):
                name = part.split(":")[0].split("=")[0].strip()
                if re.fullmatch(r"[A-Z_][A-Z0-9_]*", name):
                    used.setdefault(name, []).append((rp, line_of(code, m.start()), client))
            if client:
                findings.append(
                    finding(
                        "medium",
                        "ENV005",
                        rp,
                        line_of(code, m.start()),
                        "destructuring process.env in a Client Component: values are not inlined",
                        "write process.env.NEXT_PUBLIC_X literally at each use",
                    )
                )
        if client:
            for m in DYNAMIC_RE.finditer(code):
                findings.append(
                    finding(
                        "medium",
                        "ENV005",
                        rp,
                        line_of(code, m.start()),
                        "dynamic process.env[...] in a Client Component is always undefined",
                        "write process.env.NEXT_PUBLIC_X literally at each use",
                    )
                )
    for name, uses in sorted(used.items()):
        for rp, line, client in uses:
            if client and not name.startswith("NEXT_PUBLIC_") and name not in ("NODE_ENV",):
                sev = "high" if SECRET_NAME.search(name) else "medium"
                findings.append(
                    finding(
                        sev,
                        "ENV006",
                        rp,
                        line,
                        f"server-only variable {name} read in a Client Component (undefined in the browser"
                        + ("; keep this secret on the server)" if sev == "high" else ")"),
                        "read it in a Server Component/Action and pass only the needed result as props",
                    )
                )
    reported = {f["message"].split(" ", 1)[0].rstrip(":") for f in findings if f["rule"] in ("ENV002", "ENV003")}
    for name, uses in sorted(used.items()):
        if (
            name.startswith("NEXT_PUBLIC_")
            and name not in reported
            and SECRET_NAME.search(name[12:])
            and not PUBLIC_OK.search(name)
        ):
            rp, line, _ = uses[0]
            findings.append(
                finding(
                    "high",
                    "ENV003",
                    rp,
                    line,
                    f"{name}: secret-looking name with NEXT_PUBLIC_ prefix (shipped to every visitor)",
                    "drop the prefix and move the code that uses it to the server",
                )
            )
    if has_example:
        for name in sorted(set(used) - example_keys - NEXT_BUILTIN):
            rp, line, _ = used[name][0]
            findings.append(
                finding(
                    "low",
                    "ENV007",
                    rp,
                    line,
                    f"{name} is used but not documented in .env.example",
                    f"add `{name}=` to .env.example",
                )
            )
        for name in sorted(set(defined) - example_keys - NEXT_BUILTIN):
            findings.append(
                finding(
                    "low",
                    "ENV008",
                    ", ".join(sorted(defined[name])),
                    0,
                    f"{name} is defined but missing from .env.example",
                    f"add `{name}=` (no value) to .env.example",
                )
            )
    elif used and env_files:
        findings.append(
            finding("low", "ENV009", ".", 0, "no .env.example", "commit a .env.example with every variable name")
        )

    for cfg in ("next.config.ts", "next.config.js", "next.config.mjs", "next.config.cjs"):
        path = root / cfg
        if not path.is_file():
            continue
        code = strip_comments(read_text(path))
        m = re.search(r"\benv\s*:\s*\{", code)
        if m:
            depth, i = 0, m.end() - 1
            while i < len(code):
                depth += {"{": 1, "}": -1}.get(code[i], 0)
                if depth == 0:
                    break
                i += 1
            block = code[m.end() : i]
            for km in re.finditer(r"([A-Za-z_][A-Za-z0-9_]*)\s*:\s*process\.env\.([A-Z0-9_]+)", block):
                key, src = km.group(1), km.group(2)
                secret = SECRET_NAME.search(key) or SECRET_NAME.search(src)
                findings.append(
                    finding(
                        "high" if secret else "low",
                        "ENV010",
                        cfg,
                        line_of(code, m.end() + km.start()),
                        f"next.config env.{key} inlines process.env.{src} into client and server bundles",
                        "remove it from `env`; read process.env on the server or use NEXT_PUBLIC_ on purpose",
                    )
                )
    dockerfile = root / "Dockerfile"
    if dockerfile.is_file():
        dtext = read_text(dockerfile)
        for name in sorted(n for n in used if n.startswith("NEXT_PUBLIC_")):
            if not re.search(rf"\b(ARG|ENV)\s+{name}\b", dtext):
                findings.append(
                    finding(
                        "medium",
                        "ENV011",
                        "Dockerfile",
                        0,
                        f"{name} is inlined at build time but the Dockerfile never sets it (ARG/ENV)",
                        f"ARG {name} before `RUN npm run build` and pass --build-arg, or read it at runtime "
                        "on the server instead",
                    )
                )
    return findings


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Audit Next.js environment variable usage. Never prints values.")
    p.add_argument("path", nargs="?", default=".", help="project root (default: .)")
    p.add_argument("--json", action="store_true", help="print JSON")
    p.add_argument("--fail-on", choices=SEVERITIES, default="medium", help="exit 1 at this severity")
    args = p.parse_args(argv)
    root = Path(args.path)
    if not root.is_dir():
        print(f"error: {root} is not a directory", file=sys.stderr)
        return 2
    return emit(audit(root), args, "env audit")


if __name__ == "__main__":
    sys.exit(main())
