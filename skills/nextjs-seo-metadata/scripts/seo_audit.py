#!/usr/bin/env python3
"""Audit SEO metadata of a Next.js site, from built HTML or from App Router source.

  html MODE    scan exported/prerendered HTML (out/, .next/server/app/, any folder of .html):
               title, meta description, canonical, robots noindex, Open Graph, Twitter card,
               html lang, viewport, h1 count, JSON-LD validity, duplicate titles/descriptions.
  source MODE  scan app/ (or src/app/): pages without metadata/generateMetadata, dynamic routes
               without generateMetadata, missing metadataBase, sitemap/robots/OG image files,
               robots rules that block the whole site, metadata in Client Components, manual
               <title> tags, unescaped JSON-LD.

Read-only, offline. Exit codes: 0 = nothing at or above --fail-on, 1 = findings, 2 = usage error.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from html.parser import HTMLParser
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

SKIP_HTML = re.compile(r"(^|/)(404|500|_not-found|_error|_global-error)(\.html|/index\.html)$")


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.titles: list[str] = []
        self.meta: dict[str, list[str]] = {}
        self.links: dict[str, list[str]] = {}
        self.lang: str | None = None
        self.h1 = 0
        self.jsonld: list[str] = []
        self._in_title = False
        self._in_jsonld = False
        self._buf: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "html":
            self.lang = a.get("lang")
        elif tag == "title":
            self._in_title, self._buf = True, []
        elif tag == "meta":
            key = (a.get("name") or a.get("property") or "").lower()
            if key:
                self.meta.setdefault(key, []).append(a.get("content", ""))
        elif tag == "link":
            for r in a.get("rel", "").lower().split():
                self.links.setdefault(r, []).append(a.get("href", ""))
        elif tag == "h1":
            self.h1 += 1
        elif tag == "script" and a.get("type", "").lower() == "application/ld+json":
            self._in_jsonld, self._buf = True, []

    def handle_endtag(self, tag):
        if tag == "title" and self._in_title:
            self.titles.append("".join(self._buf).strip())
            self._in_title = False
        elif tag == "script" and self._in_jsonld:
            self.jsonld.append("".join(self._buf))
            self._in_jsonld = False

    def handle_data(self, data):
        if self._in_title or self._in_jsonld:
            self._buf.append(data)


def audit_html_page(text: str, rp: str) -> tuple[list[dict], dict]:
    p = PageParser()
    p.feed(text)
    out: list[dict] = []

    def add(sev, rule, msg, fix=""):
        out.append(finding(sev, rule, rp, 0, msg, fix))

    title = p.titles[0] if p.titles else ""
    desc = (p.meta.get("description") or [""])[0].strip()
    robots = " ".join(p.meta.get("robots", [])).lower()
    noindex = "noindex" in robots
    if not title:
        add("high", "SEO001", "missing or empty <title>", "export metadata.title or generateMetadata")
    elif len(title) > 65:
        add("low", "SEO002", f"title is {len(title)} chars (search results show about 60)")
    if len(p.titles) > 1:
        add("medium", "SEO003", f"{len(p.titles)} <title> tags", "remove manual <title>; use the Metadata API")
    if not desc:
        add("medium", "SEO004", "missing meta description", "set metadata.description")
    elif len(desc) < 50 or len(desc) > 170:
        add("low", "SEO005", f"meta description is {len(desc)} chars (aim for 70-160)")
    canon = p.links.get("canonical", [])
    if not canon and not noindex:
        add("medium", "SEO006", "no canonical URL", "metadata.alternates.canonical (with metadataBase)")
    elif canon and not re.match(r"^https?://", canon[0]):
        add(
            "medium",
            "SEO007",
            f"canonical is not absolute: {canon[0]!r}",
            "set metadataBase in the root layout",
        )
    if noindex:
        add("info", "SEO008", "page is noindex (intended?)")
    for key in ("og:title", "og:description", "og:image"):
        if not p.meta.get(key):
            add("low" if key != "og:image" else "medium", "SEO009", f"missing {key}", "metadata.openGraph")
    for img in p.meta.get("og:image", []):
        if img and not re.match(r"^https?://", img):
            add(
                "high",
                "SEO010",
                f"og:image is a relative URL ({img!r}); crawlers ignore it",
                "set metadataBase",
            )
    if not p.meta.get("twitter:card"):
        add("low", "SEO011", "missing twitter:card", "metadata.twitter = { card: 'summary_large_image' }")
    if not p.lang:
        add("medium", "SEO012", "<html> has no lang attribute", '<html lang="en"> in app/layout.tsx')
    if not p.meta.get("viewport"):
        add("low", "SEO013", "missing viewport meta")
    if p.h1 == 0:
        add("low", "SEO014", "no <h1> on the page")
    elif p.h1 > 1:
        add("info", "SEO014", f"{p.h1} <h1> elements")
    for block in p.jsonld:
        try:
            data = json.loads(block)
        except json.JSONDecodeError as exc:
            add("high", "SEO015", f"JSON-LD does not parse: {exc.msg} (line {exc.lineno})")
            continue
        items = data if isinstance(data, list) else data.get("@graph", [data]) if isinstance(data, dict) else []
        if isinstance(data, dict) and "@context" not in data:
            add("medium", "SEO016", "JSON-LD without @context", '"@context": "https://schema.org"')
        for item in items:
            if isinstance(item, dict) and "@type" not in item:
                add("medium", "SEO016", "JSON-LD item without @type")
    return out, {"title": title, "description": desc, "noindex": noindex}


def audit_html_dir(root: Path) -> list[dict]:
    findings: list[dict] = []
    titles: dict[str, list[str]] = {}
    descs: dict[str, list[str]] = {}
    files = list(iter_files(root, (".html",)))
    for path in files:
        rp = rel(path, root)
        if SKIP_HTML.search(rp):
            continue
        page_findings, info = audit_html_page(read_text(path), rp)
        findings += page_findings
        if not info["noindex"]:
            if info["title"]:
                titles.setdefault(info["title"], []).append(rp)
            if info["description"]:
                descs.setdefault(info["description"], []).append(rp)
    for label, table, rule in (("title", titles, "SEO017"), ("meta description", descs, "SEO018")):
        for pages in table.values():
            if len(pages) > 1:
                findings.append(
                    finding(
                        "medium",
                        rule,
                        pages[0],
                        0,
                        f"duplicate {label} on {len(pages)} pages: {', '.join(pages[:5])}"
                        + (" ..." if len(pages) > 5 else ""),
                        f"give each page its own {label} (generateMetadata for dynamic routes)",
                    )
                )
    if not files:
        findings.append(finding("high", "SEO000", rel(root, root), 0, "no .html files found", ""))
    return findings


def _route_files(app: Path, stem: str):
    for path in iter_files(app):
        if path.name.split(".")[0] == stem and path.suffix in (".tsx", ".jsx", ".ts", ".js", ".mdx"):
            yield path


def _has_metadata(code: str) -> bool:
    return bool(re.search(r"export\s+(const\s+metadata\b|(async\s+)?function\s+generateMetadata\b)", code))


def audit_source(root: Path) -> list[dict]:
    app = next((c for c in (root / "app", root / "src" / "app") if c.is_dir()), None)
    if app is None:
        return [finding("high", "SEO000", ".", 0, "no app/ or src/app/ directory found (App Router only)")]
    findings: list[dict] = []
    layouts = {p.parent: strip_comments(read_text(p)) for p in _route_files(app, "layout")}
    root_layout = layouts.get(app, "")
    any_meta = any(_has_metadata(c) for c in layouts.values())
    for page in _route_files(app, "page"):
        code = strip_comments(read_text(page))
        rp = rel(page, root)
        if directive(code) == "client" and _has_metadata(code):
            findings.append(finding("high", "SEO020", rp, 0, "metadata exported from a Client Component is ignored"))
        own = _has_metadata(code)
        any_meta = any_meta or own
        segs = page.relative_to(app).parts[:-1]
        dynamic = any(s.startswith("[") for s in segs)
        if dynamic and "generateMetadata" not in code:
            findings.append(
                finding(
                    "medium",
                    "SEO021",
                    rp,
                    0,
                    "dynamic route without generateMetadata: every page shares the parent title/description",
                    "export async function generateMetadata({ params }) { const { slug } = await params; ... }",
                )
            )
        elif not own and not dynamic:
            inherited = any(_has_metadata(c) for d, c in layouts.items() if d == page.parent or d in page.parents)
            findings.append(
                finding(
                    "low" if inherited else "medium",
                    "SEO022",
                    rp,
                    0,
                    "page has no metadata export"
                    + (" (inherits the layout title)" if inherited else " and no layout provides any"),
                    "export const metadata = { title: '...', description: '...' }",
                )
            )
        m = re.search(r"<title>", code)
        if m:
            findings.append(
                finding(
                    "low",
                    "SEO023",
                    rp,
                    line_of(code, m.start()),
                    "manual <title> in JSX",
                    "use the Metadata API",
                )
            )
    for path in iter_files(app):
        code = strip_comments(read_text(path))
        m = re.search(r"application/ld\+json", code)
        if m and "JSON.stringify" in code and not re.search(r"\\\\u003c|replace\(\s*/<", code):
            findings.append(
                finding(
                    "low",
                    "SEO024",
                    rel(path, root),
                    line_of(code, m.start()),
                    "JSON-LD injected with JSON.stringify without escaping '<' (XSS if data is user-controlled)",
                    "JSON.stringify(data).replace(/</g, '\\\\u003c')",
                )
            )
    if any_meta and "metadataBase" not in root_layout:
        findings.append(
            finding(
                "medium",
                "SEO025",
                rel(app / "layout.tsx", root),
                0,
                "root layout has no metadataBase: canonical/OG URLs resolve against localhost",
                "export const metadata = { metadataBase: new URL('https://example.com'), ... }",
            )
        )
    if root_layout and not re.search(r"<html[^>]*\slang=", root_layout):
        findings.append(finding("medium", "SEO012", rel(app, root) + "/layout", 0, "<html> without lang"))
    public = root / "public"
    has = {
        "sitemap": any(app.glob("sitemap.*")) or (public / "sitemap.xml").is_file() or any(app.glob("**/sitemap.*")),
        "robots": any(app.glob("robots.*")) or (public / "robots.txt").is_file(),
        "og": any(app.glob("**/opengraph-image.*")) or "openGraph" in root_layout,
    }
    if not has["sitemap"]:
        findings.append(
            finding("medium", "SEO026", "app/", 0, "no sitemap", "add app/sitemap.ts (MetadataRoute.Sitemap)")
        )
    if not has["robots"]:
        findings.append(
            finding("medium", "SEO027", "app/", 0, "no robots file", "add app/robots.ts (MetadataRoute.Robots)")
        )
    if not has["og"]:
        findings.append(
            finding(
                "low",
                "SEO028",
                "app/",
                0,
                "no default Open Graph image",
                "add app/opengraph-image.tsx or .png",
            )
        )
    for robots in [*app.glob("robots.*"), public / "robots.txt"]:
        if robots.is_file() and blocks_everything(read_text(robots), robots.suffix == ".txt"):
            text = read_text(robots)
            gated = robots.suffix != ".txt" and "process.env" in text and re.search(r"\bif\b|\?", text)
            findings.append(
                finding(
                    "medium" if gated else "high",
                    "SEO029",
                    rel(robots, root),
                    0,
                    "robots rules can disallow '/' for all crawlers"
                    + (
                        " (env-gated: confirm production serves the allow branch)"
                        if gated
                        else " (site drops out of search)"
                    ),
                    "only disallow private paths; gate staging with an env check instead",
                )
            )
    return findings


def blocks_everything(text: str, is_txt: bool) -> bool:
    """True when robots rules disallow '/' for user-agent '*'."""
    if is_txt:
        agents: list[str] = []
        in_rules = False
        for raw in text.splitlines():
            line = raw.split("#", 1)[0].strip()
            if ":" not in line:
                continue
            key, value = (x.strip() for x in line.split(":", 1))
            key = key.lower()
            if key == "user-agent":
                if in_rules:
                    agents, in_rules = [], False
                agents.append(value)
            elif key in ("allow", "disallow"):
                in_rules = True
                if key == "disallow" and value == "/" and "*" in agents:
                    return True
        return False
    code = strip_comments(text)
    return bool(
        re.search(r"userAgent\s*:\s*['\"]\*['\"]", code) and re.search(r"disallow\s*:\s*(\[\s*)?['\"]/['\"]", code)
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Audit Next.js SEO metadata from built HTML or App Router source.")
    p.add_argument("mode", choices=["html", "source"], help="html: built pages; source: app/ directory")
    p.add_argument("path", help="HTML folder (out/, .next/server/app) or project root")
    p.add_argument("--json", action="store_true", help="print JSON")
    p.add_argument("--fail-on", choices=SEVERITIES, default="medium", help="exit 1 at this severity")
    args = p.parse_args(argv)
    root = Path(args.path)
    if not root.exists():
        print(f"error: {root} does not exist", file=sys.stderr)
        return 2
    findings = audit_html_dir(root) if args.mode == "html" else audit_source(root)
    return emit(findings, args, f"seo audit ({args.mode})")


if __name__ == "__main__":
    sys.exit(main())
