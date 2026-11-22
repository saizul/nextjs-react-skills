#!/usr/bin/env python3
"""Scan Next.js Server Actions and mutating route handlers for missing security checks.

Finds every Server Action (exported async functions in "use server" files and inline
functions with a "use server" directive) and every POST/PUT/PATCH/DELETE route handler, then
reports, per function:
  * no authentication call (auth(), getServerSession(), currentUser(), verifySession(), ...)
  * takes input but never validates it (zod .parse/.safeParse, valibot, yup, ...)
  * redirect() to a user-controlled value (open redirect)
  * auth-sensitive actions (login, signup, reset, contact, ...) without rate limiting
  * error messages or stack traces returned to the client
  * cookie-authenticated route handlers without an Origin/CSRF check
and in next.config: serverActions.allowedOrigins containing "*", very large bodySizeLimit.

Mark an intentionally public function (login, contact form, webhook) with a comment inside
it or on the two lines above it: // action-scan: public  (skips only the authentication check)
Add project helpers with --auth-pattern / --validate-pattern (regular expressions).

Heuristic and read-only. Exit codes: 0 = nothing at or above --fail-on, 1 = findings, 2 = usage error.
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

AUTH_PATTERNS = [
    r"\bauth\s*\(",
    r"\bgetServerSession\s*\(",
    r"\bcurrentUser\s*\(",
    r"\bgetCurrentUser\s*\(",
    r"\bgetUser\s*\(",
    r"\bgetSession\s*\(",
    r"\bverifySession\s*\(",
    r"\bvalidateRequest\s*\(",
    r"\brequire(User|Auth|Session|Admin|Role)\w*\s*\(",
    r"\bassert(User|Auth|Session|Admin)\w*\s*\(",
    r"\bgetAuth\s*\(",
    r"\bauth\.(api\.)?getSession\s*\(",
    r"\.auth\.getUser\s*\(",
    r"\bwithAuth\b",
    r"\bauthActionClient\b|\bauthedAction\b|\bprotectedAction\b",
]
VALIDATE_PATTERNS = [
    r"\.(safeParse|parse|parseAsync|safeParseAsync)\s*\(",
    r"\bv\.(parse|safeParse)\s*\(",
    r"\b(validate|validateSync|isValid)\s*\(",
    r"\.inputSchema\s*\(|\.schema\s*\(",
    r"\bparseWithZod\s*\(|\bparseFormData\s*\(",
]
RATE_LIMIT = re.compile(r"rate.?limit|ratelimit|limiter|throttle|slidingWindow|tokenBucket", re.I)
SENSITIVE_NAME = re.compile(
    r"(log.?in|sign.?in|sign.?up|register|reset|forgot|password|otp|verify|magic|contact|subscribe|"
    r"newsletter|invite|comment|feedback|upload)",
    re.I,
)
USER_REDIRECT = re.compile(
    r"\bredirect\s*\(\s*(?!['\"`/])([^)]*(formData\.get|searchParams|callbackUrl|returnTo|redirectTo|"
    r"\bnext\b|\burl\b|input\.|data\.|params)[^)]*)\)"
)
ERROR_LEAK = re.compile(r"return\s*\{?[^;}]*\b(e|err|error)\.(message|stack)\b|return\s+(e|err|error)\s*[;}]")
PUBLIC_MARK = re.compile(r"action-scan:\s*public")
MUTATING = ("POST", "PUT", "PATCH", "DELETE")


def match_pair(code: str, start: int, open_c: str, close_c: str) -> int:
    """Index just past the bracket matching code[start] (skips strings)."""
    depth, i, n, quote = 0, start, len(code), None
    while i < n:
        c = code[i]
        if quote:
            if c == "\\":
                i += 2
                continue
            if c == quote:
                quote = None
        elif c in "'\"`":
            quote = c
        elif c == open_c:
            depth += 1
        elif c == close_c:
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return n


def extract_functions(code: str, inline_only: bool):
    """Yield (name, start, end, params, body) for server-action candidates."""
    if inline_only:
        pattern = re.compile(
            r"async\s+function\s+(?P<n1>\w+)\s*(?=\()|(?:const|let)\s+(?P<n2>\w+)\s*=\s*async\s*(?=\()"
        )
    else:
        pattern = re.compile(
            r"export\s+(?:default\s+)?async\s+function\s*(?P<n1>\w*)\s*(?=\()|"
            r"export\s+(?:const|let)\s+(?P<n2>\w+)\s*=\s*async\s*(?=\()"
        )
    for m in pattern.finditer(code):
        name = m.group("n1") or m.group("n2") or "default"
        p_start = m.end()
        p_end = match_pair(code, p_start, "(", ")")
        params = code[p_start + 1 : p_end - 1].strip()
        rest = code[p_end:]
        bm = re.match(r"\s*(:\s*[^={]+)?\s*(=>)?\s*\{", rest)
        if bm:
            b_start = p_end + bm.end() - 1
            b_end = match_pair(code, b_start, "{", "}")
            body = code[b_start:b_end]
        else:
            b_end = p_end + len(rest.split("\n", 1)[0])
            body = code[p_end:b_end]
        if inline_only and not re.match(r"\{\s*['\"]use server['\"]", body):
            continue
        yield name, m.start(), b_end, params, body


def check_body(kind, name, params, body, raw_ctx, auth_re, val_re, rp, line, cookie_auth=False):
    out = []
    public = bool(PUBLIC_MARK.search(raw_ctx))
    label = f"{kind} '{name}'"
    has_auth = bool(auth_re.search(body))
    if not has_auth and not public:
        out.append(
            finding(
                "high",
                "SA001",
                rp,
                line,
                f"{label} has no authentication check (anyone can call it with a POST request)",
                "const session = await auth(); if (!session) throw new Error('Unauthorized') "
                "- then check the user may touch this record",
            )
        )
    takes_input = bool(params) and not re.fullmatch(r"\(?\s*\)?", params)
    if kind == "route handler":
        takes_input = bool(re.search(r"\.(json|formData|text)\s*\(\s*\)|searchParams", body))
    if takes_input and not val_re.search(body):
        out.append(
            finding(
                "high" if re.search(r"\b(db|prisma|sql|insert|update|delete|create)\w*\b", body, re.I) else "medium",
                "SA002",
                rp,
                line,
                f"{label} reads input without schema validation (TypeScript types are not checked at runtime)",
                "const parsed = Schema.safeParse(Object.fromEntries(formData)); if (!parsed.success) return ...",
            )
        )
    m = USER_REDIRECT.search(body)
    if m:
        out.append(
            finding(
                "medium",
                "SA003",
                rp,
                line,
                f"{label} redirects to a user-controlled value: redirect({m.group(1).strip()[:60]})",
                "allow only relative paths: if (!to.startsWith('/') || to.startsWith('//')) to = '/'",
            )
        )
    if SENSITIVE_NAME.search(name) and not RATE_LIMIT.search(body):
        out.append(
            finding(
                "medium",
                "SA004",
                rp,
                line,
                f"{label} looks abuse-prone (auth/contact/upload) but has no rate limit",
                "limit by IP and account (e.g. @upstash/ratelimit, or a Redis/DB counter) before doing work",
            )
        )
    m = ERROR_LEAK.search(body)
    if m:
        out.append(
            finding(
                "low",
                "SA005",
                rp,
                line,
                f"{label} returns raw error details to the client",
                "log the error server-side and return a generic message",
            )
        )
    if (
        kind == "route handler"
        and cookie_auth
        and not re.search(r"get\(\s*['\"]origin['\"]\s*\)|csrf|sec-fetch-site", body + raw_ctx, re.I)
    ):
        out.append(
            finding(
                "medium",
                "SA006",
                rp,
                line,
                f"{label} uses cookie auth but has no Origin/CSRF check (route handlers get none built in)",
                "compare request.headers.get('origin') with your host, or require a non-cookie token",
            )
        )
    return out


def context(raw: str, start: int, end: int) -> str:
    """The function text plus the two lines above it (where a public marker comment goes)."""
    head = raw[:start].rsplit("\n", 3)
    return "\n".join(head[-3:]) + raw[start:end]


def scan_file(path: Path, root: Path, auth_re, val_re) -> list[dict]:
    raw = read_text(path)
    code = strip_comments(raw)
    rp = rel(path, root)
    findings: list[dict] = []
    if directive(code) == "server":
        funcs = list(extract_functions(code, inline_only=False))
        for name, start, end, params, body in funcs:
            ctx = context(raw, start, end)
            findings += check_body("server action", name, params, body, ctx, auth_re, val_re, rp, line_of(code, start))
    elif "use server" in code:
        for name, start, end, params, body in extract_functions(code, inline_only=True):
            ctx = context(raw, start, end)
            findings += check_body(
                "inline server action", name, params, body, ctx, auth_re, val_re, rp, line_of(code, start)
            )
    if path.name.split(".")[0] == "route" and "app" in path.parts:
        cookie_auth = bool(re.search(r"\bcookies\s*\(|getServerSession|\bauth\s*\(|session", code))
        for method in MUTATING:
            m = re.search(
                rf"export\s+(?:async\s+)?function\s+{method}\s*(?=\()|export\s+const\s+{method}\s*=\s*(?:async\s*)?(?=\()",
                code,
            )
            if not m:
                continue
            p_end = match_pair(code, m.end(), "(", ")")
            b = code.find("{", p_end)
            end = match_pair(code, b, "{", "}") if b != -1 else p_end
            body = code[b:end] if b != -1 else ""
            ctx = context(raw, m.start(), end)
            findings += check_body(
                "route handler",
                method,
                code[m.end() + 1 : p_end - 1],
                body,
                ctx,
                auth_re,
                val_re,
                rp,
                line_of(code, m.start()),
                cookie_auth,
            )
    return findings


def scan_config(root: Path) -> list[dict]:
    out = []
    for name in ("next.config.ts", "next.config.js", "next.config.mjs", "next.config.cjs"):
        path = root / name
        if not path.is_file():
            continue
        code = strip_comments(read_text(path))
        m = re.search(r"allowedOrigins\s*:\s*\[[^\]]*['\"]\*\*?['\"]", code)
        if m:
            out.append(
                finding(
                    "high",
                    "SA010",
                    name,
                    line_of(code, m.start()),
                    "serverActions.allowedOrigins contains '*' (disables the built-in CSRF protection)",
                    "list exact proxy/front-end hosts, e.g. ['app.example.com']",
                )
            )
        m = re.search(r"bodySizeLimit\s*:\s*['\"]?(\d+)\s*(mb|gb)", code, re.I)
        if m and (m.group(2).lower() == "gb" or int(m.group(1)) > 20):
            out.append(
                finding(
                    "low",
                    "SA011",
                    name,
                    line_of(code, m.start()),
                    f"serverActions.bodySizeLimit is {m.group(1)}{m.group(2)} (default 1mb); easy memory DoS",
                    "keep it small; upload large files directly to object storage with signed URLs",
                )
            )
    return out


def scan(root: Path, extra_auth=(), extra_validate=()) -> list[dict]:
    auth_re = re.compile("|".join([*AUTH_PATTERNS, *extra_auth]))
    val_re = re.compile("|".join([*VALIDATE_PATTERNS, *extra_validate]))
    findings: list[dict] = []
    for path in iter_files(root):
        findings += scan_file(path, root, auth_re, val_re)
    if root.is_dir():
        findings += scan_config(root)
    return findings


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Flag Next.js Server Actions and route handlers without auth, validation or rate limits."
    )
    p.add_argument("path", nargs="?", default=".", help="project root or file (default: .)")
    p.add_argument("--auth-pattern", action="append", default=[], help="extra regex that counts as an auth check")
    p.add_argument(
        "--validate-pattern", action="append", default=[], help="extra regex that counts as input validation"
    )
    p.add_argument("--json", action="store_true", help="print JSON")
    p.add_argument("--fail-on", choices=SEVERITIES, default="medium", help="exit 1 at this severity")
    args = p.parse_args(argv)
    root = Path(args.path)
    if not root.exists():
        print(f"error: {root} does not exist", file=sys.stderr)
        return 2
    try:
        findings = scan(root, args.auth_pattern, args.validate_pattern)
    except re.error as exc:
        print(f"error: bad pattern: {exc}", file=sys.stderr)
        return 2
    return emit(findings, args, "server action scan")


if __name__ == "__main__":
    sys.exit(main())
