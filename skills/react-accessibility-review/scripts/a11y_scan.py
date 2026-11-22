#!/usr/bin/env python3
"""Static accessibility scan of React / Next.js JSX and TSX files.

Reports the issues that are reliably detectable without rendering:
  * <img>, next/image <Image> and <input type="image"> without alt; redundant alt text
  * click handlers on non-interactive elements (div, span, li, ...) without role, tabIndex
    or keyboard handler; <a> used as a button (no href, href="#", javascript:)
  * icon-only <button>/<a>/<Link> with no text and no aria-label
  * form fields (input, select, textarea) with no label, aria-label or aria-labelledby
  * positive tabIndex, autoFocus, aria-hidden on focusable elements
  * <html> without lang, <iframe> without title

Heuristic (no type information): spread props such as {...props} may supply attributes, so
those elements are skipped for that check. Read-only.
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

JSX_EXTS = (".jsx", ".tsx", ".js")
TAG_START = re.compile(r"<([A-Za-z][\w.:-]*)")
NON_INTERACTIVE = {
    "div",
    "span",
    "li",
    "p",
    "section",
    "article",
    "td",
    "tr",
    "img",
    "svg",
    "main",
    "header",
    "footer",
    "ul",
    "label",
}
FIELDS = {"input", "select", "textarea"}
UNLABELLED_INPUT_TYPES = {"hidden", "submit", "button", "reset", "image"}
REDUNDANT_ALT = re.compile(r"^(image|picture|photo|graphic|icon)( of)?\b|\.(png|jpe?g|webp|gif|svg|avif)$", re.I)


def iter_tags(code: str):
    """Yield (name, start, attrs_text, self_closing, end) for JSX opening tags."""
    n = len(code)
    for m in TAG_START.finditer(code):
        j = m.start() - 1
        while j >= 0 and code[j] in " \t\r\n":
            j -= 1
        prev = code[j] if j >= 0 else ""
        # foo<Bar> / fn()<T> without a space is a TypeScript generic, not JSX
        if j == m.start() - 1 and prev and (prev.isalnum() or prev in "_$.)]\"'"):
            continue
        i, depth, quote = m.end(), 0, None
        while i < n:
            c = code[i]
            if quote:
                if c == "\\":
                    i += 2
                    continue
                if c == quote:
                    quote = None
            elif c in "\"'" or (c == "`" and depth > 0):
                quote = c
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
            elif c in "<>" and depth == 0:
                break
            i += 1
        if i >= n or code[i] != ">":
            continue
        attrs = code[m.end() : i]
        yield m.group(1), m.start(), attrs, attrs.rstrip().endswith("/"), i + 1


def parse_attrs(text: str) -> tuple[dict, list[str]]:
    """Return ({name: value-or-True}, [spread expressions]) for an attribute string."""
    attrs: dict = {}
    spreads: list[str] = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c.isspace() or c == "/":
            i += 1
            continue
        if c == "{":
            end = _match_brace(text, i)
            inner = text[i + 1 : end - 1].strip()
            if inner.startswith("..."):
                spreads.append(inner[3:].strip())
            i = end
            continue
        m = re.match(r"[A-Za-z_][\w:.-]*", text[i:])
        if not m:
            i += 1
            continue
        name = m.group(0)
        i += m.end()
        while i < n and text[i].isspace():
            i += 1
        if i < n and text[i] == "=":
            i += 1
            while i < n and text[i].isspace():
                i += 1
            if i < n and text[i] in "\"'":
                q = text[i]
                end = text.find(q, i + 1)
                end = n if end == -1 else end
                attrs[name] = text[i + 1 : end]
                i = end + 1
            elif i < n and text[i] == "{":
                end = _match_brace(text, i)
                attrs[name] = "{" + text[i + 1 : end - 1].strip() + "}"
                i = end
            else:
                attrs[name] = True
        else:
            attrs[name] = True
    return attrs, spreads


def _match_brace(text: str, start: int) -> int:
    depth, i, quote = 0, start, None
    while i < len(text):
        c = text[i]
        if quote:
            if c == "\\":
                i += 2
                continue
            if c == quote:
                quote = None
        elif c in "\"'`":
            quote = c
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return len(text)


def children_of(code: str, name: str, end: int) -> str:
    """Text between an opening tag (ending at `end`) and its matching closing tag."""
    depth, pos = 1, end
    pat = re.compile(rf"<{re.escape(name)}(?=[\s>/])|</{re.escape(name)}\s*>")
    for m in pat.finditer(code, end):
        if m.group(0).startswith("</"):
            depth -= 1
            if depth == 0:
                return code[pos : m.start()]
        else:
            depth += 1
    return ""


def has_text(content: str) -> bool:
    stripped = re.sub(r"<[^>]*>", " ", content)
    return bool(stripped.strip())


def opaque_spread(spreads: list[str]) -> bool:
    """A spread like {...props} may carry any attribute; {...register('x')} does not carry labels."""
    return any(re.fullmatch(r"[A-Za-z_$][\w$.]*", s) for s in spreads)


def truthy(value) -> bool:
    return value is True or str(value).strip("{}").strip("'\"") in ("true", "")


def scan_code(code: str, rp: str) -> list[dict]:
    out: list[dict] = []
    tags = list(iter_tags(code))
    label_for = set()
    for name, _, attrs_text, _, _ in tags:
        if name in ("label", "Label") or "htmlFor" in attrs_text:
            attrs, _ = parse_attrs(attrs_text)
            v = attrs.get("htmlFor")
            if isinstance(v, str):
                label_for.add(v.strip("{}").strip("'\"`"))

    def add(sev, rule, start, msg, fix=""):
        out.append(finding(sev, rule, rp, line_of(code, start), msg, fix))

    for name, start, attrs_text, self_closing, end in tags:
        attrs, spreads = parse_attrs(attrs_text)
        opaque = opaque_spread(spreads)
        lname = name.lower() if name[0].islower() else name
        labelled = any(k in attrs for k in ("aria-label", "aria-labelledby", "title"))
        content = "" if self_closing else children_of(code, name, end)

        is_img = lname == "img" or name == "Image" or (lname == "input" and attrs.get("type") == "image")
        if is_img:
            if "alt" not in attrs and not opaque:
                add(
                    "high",
                    "A11Y001",
                    start,
                    f"<{name}> without alt",
                    'describe the image (alt="Team photo at the 2026 offsite") or alt="" if decorative',
                )
            elif isinstance(attrs.get("alt"), str) and REDUNDANT_ALT.search(attrs["alt"].strip()):
                add("low", "A11Y002", start, f"redundant alt text {attrs['alt']!r}", "describe what it shows")

        if "onClick" in attrs and lname in NON_INTERACTIVE:
            role = attrs.get("role")
            if not role:
                add(
                    "high",
                    "A11Y003",
                    start,
                    f"<{name} onClick> is not keyboard or screen-reader accessible",
                    'use <button type="button"> (or <Link>/<a href> for navigation)',
                )
            else:
                if "tabIndex" not in attrs and not opaque:
                    add(
                        "medium",
                        "A11Y004",
                        start,
                        f'<{name} role="{role}"> with onClick but no tabIndex',
                        "tabIndex={0}",
                    )
                if not any(k in attrs for k in ("onKeyDown", "onKeyUp", "onKeyPress")) and not opaque:
                    add(
                        "medium",
                        "A11Y005",
                        start,
                        f'<{name} role="{role}"> with onClick but no keyboard handler',
                        "handle Enter and Space in onKeyDown, or use a real <button>",
                    )

        if lname == "a":
            href = attrs.get("href")
            bad_href = href is None or (
                isinstance(href, str) and (href.strip() in ("#", "") or href.startswith("javascript:"))
            )
            if "onClick" in attrs and bad_href and not opaque:
                add("high", "A11Y006", start, "<a> used as a button (no real href)", '<button type="button">')

        if lname in ("button", "a") or name == "Link":
            if not labelled and not opaque and not has_text(content) and "{" not in re.sub(r"<[^>]*>", "", content):
                add(
                    "high",
                    "A11Y007",
                    start,
                    f"<{name}> has no accessible name (icon-only?)",
                    'add aria-label="Close" or visually hidden text (<span className="sr-only">Close</span>)',
                )

        if lname in FIELDS:
            itype = attrs.get("type", "text") if isinstance(attrs.get("type", "text"), str) else "text"
            if itype not in UNLABELLED_INPUT_TYPES and not labelled and not opaque:
                fid = attrs.get("id")
                fid = fid.strip("{}").strip("'\"`") if isinstance(fid, str) else None
                before = code[:start]
                wrapped = before.rfind("<label") > before.rfind("</label") or before.rfind("<Label") > before.rfind(
                    "</Label"
                )
                if not (fid and fid in label_for) and not wrapped:
                    hint = " (placeholder is not a label)" if "placeholder" in attrs else ""
                    add(
                        "medium",
                        "A11Y008",
                        start,
                        f"<{name}> has no associated label{hint}",
                        '<label htmlFor="email">Email</label> + id="email", or aria-label',
                    )

        tab = attrs.get("tabIndex")
        if tab is not None:
            m = re.search(r"-?\d+", str(tab))
            if m and int(m.group(0)) > 0:
                add(
                    "medium",
                    "A11Y009",
                    start,
                    f"positive tabIndex ({m.group(0)}) breaks the natural tab order",
                    "use 0 or -1",
                )
        if "autoFocus" in attrs:
            add(
                "low",
                "A11Y010",
                start,
                "autoFocus moves focus unexpectedly for screen-reader users",
                "remove unless it is a dialog's first field",
            )
        focusable = (
            lname in ("button", "input", "select", "textarea") or (lname == "a" and "href" in attrs) or name == "Link"
        )
        if focusable and truthy(attrs.get("aria-hidden", "false")) and "aria-hidden" in attrs:
            add(
                "high",
                "A11Y011",
                start,
                f"aria-hidden on focusable <{name}>",
                "remove aria-hidden or make it unfocusable (tabIndex={-1})",
            )
        if lname == "html" and "lang" not in attrs:
            add("high", "A11Y012", start, "<html> without lang", '<html lang="en">')
        if lname == "iframe" and "title" not in attrs and not opaque:
            add("medium", "A11Y013", start, "<iframe> without title", 'title="Map of our office"')
    return out


def scan(root: Path) -> list[dict]:
    findings: list[dict] = []
    for path in iter_files(root, JSX_EXTS):
        code = strip_comments(read_text(path))
        if "<" not in code:
            continue
        findings += scan_code(code, rel(path, root))
    return findings


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Static accessibility scan for React/Next.js JSX/TSX.")
    p.add_argument("path", nargs="?", default=".", help="project root, folder or file (default: .)")
    p.add_argument("--json", action="store_true", help="print JSON")
    p.add_argument("--fail-on", choices=SEVERITIES, default="medium", help="exit 1 at this severity")
    args = p.parse_args(argv)
    root = Path(args.path)
    if not root.exists():
        print(f"error: {root} does not exist", file=sys.stderr)
        return 2
    return emit(scan(root), args, "a11y scan")


if __name__ == "__main__":
    sys.exit(main())
