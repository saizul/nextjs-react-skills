#!/usr/bin/env python3
"""Report JavaScript bundle size problems for a Next.js / React build.

Three inputs (use whichever you have):
  --build-log FILE   saved `next build` output from Next.js 13-15 (route table with
                     "Size" and "First Load JS"; Next.js 16 no longer prints sizes)
  --stats FILE       webpack stats JSON (webpack-bundle-analyzer generateStatsFile, or
                     stats.toJson() from a webpack build): largest assets and modules,
                     known heavy packages, duplicated packages
  --next-dir DIR     a built .next directory: measures .next/static/chunks (raw + gzip) and,
                     when build manifests are present, JS per route

Flags routes whose first-load JS (gzip) exceeds --warn-kb / --fail-kb and single chunks
larger than --chunk-kb. Read-only. Exit codes: 0 = nothing at or above --fail-on,
1 = findings, 2 = usage error.
"""

from __future__ import annotations

import argparse
import gzip
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

UNITS = {"b": 1 / 1000, "kb": 1.0, "mb": 1000.0}
ROUTE_LINE = re.compile(
    r"^[\s│]*[┌├└]\s+(?P<sym>[○●ƒλ◐◇]|\(\w+\))?\s*(?P<route>/\S*)\s+"
    r"(?P<size>[\d.]+)\s*(?P<su>B|kB|MB)\s+(?P<first>[\d.]+)\s*(?P<fu>B|kB|MB)\s*$"
)
SHARED_LINE = re.compile(r"First Load JS shared by all\s+(?P<v>[\d.]+)\s*(?P<u>B|kB|MB)")
HEAVY = {
    "moment": "date-fns or dayjs (or Intl.DateTimeFormat)",
    "lodash": "lodash-es with per-function imports, or native methods",
    "@mui/icons-material": "import each icon by path: @mui/icons-material/Delete",
    "react-icons": "import from the specific icon set path and check tree shaking",
    "chart.js": "load the chart with next/dynamic(..., { ssr: false }) below the fold",
    "three": "next/dynamic for the 3D scene; keep it off the critical path",
    "firebase": "modular v9+ imports (firebase/auth) and lazy-load",
    "aws-sdk": "AWS SDK v3 modular clients, on the server only",
    "highlight.js": "highlight on the server (rehype) or load only needed languages",
    "core-js": "drop legacy polyfills; Next.js already polyfills for supported browsers",
    "crypto-js": "Web Crypto API (crypto.subtle)",
    "jquery": "native DOM APIs / React state",
    "@fortawesome/fontawesome-free": "SVG icons per component",
    "xlsx": "parse spreadsheets on the server or lazy-load on click",
    "pdfjs-dist": "lazy-load the viewer with next/dynamic",
}


def to_kb(value: str, unit: str) -> float:
    return float(value) * UNITS[unit.lower()]


def parse_build_log(text: str) -> dict:
    routes = []
    shared = None
    for line in text.splitlines():
        m = ROUTE_LINE.match(line)
        if m:
            routes.append(
                {
                    "route": m.group("route"),
                    "type": m.group("sym") or "",
                    "size_kb": round(to_kb(m.group("size"), m.group("su")), 2),
                    "first_load_kb": round(to_kb(m.group("first"), m.group("fu")), 2),
                }
            )
        m = SHARED_LINE.search(line)
        if m:
            shared = round(to_kb(m.group("v"), m.group("u")), 2)
    return {"routes": routes, "shared_kb": shared}


def check_routes(routes, shared_kb, warn_kb, fail_kb, src) -> list[dict]:
    out = []
    for r in routes:
        first = r["first_load_kb"]
        if r["route"].startswith("/api") or first == 0:
            continue
        if first >= fail_kb:
            sev = "high"
        elif first >= warn_kb:
            sev = "medium"
        else:
            continue
        out.append(
            finding(
                sev,
                "PERF001",
                src,
                0,
                f"route {r['route']} loads {first:.0f} kB JS on first visit (budget {warn_kb:.0f} kB)",
                "move client-only widgets behind next/dynamic, keep data fetching in Server Components, "
                "and check the route's largest modules with the bundle analyzer",
            )
        )
    if shared_kb is not None and shared_kb > warn_kb * 0.7:
        out.append(
            finding(
                "medium",
                "PERF002",
                src,
                0,
                f"JS shared by all routes is {shared_kb:.0f} kB",
                "look for providers/libraries imported in the root layout that only some pages need",
            )
        )
    return out


def package_of(name: str) -> str | None:
    m = re.findall(r"node_modules/((?:@[^/]+/)?[^/]+)", name.replace("\\", "/"))
    return m[-1] if m else None


def analyze_stats(data: dict, chunk_kb: float, src: str) -> tuple[list[dict], dict]:
    out = []
    if "children" in data and not data.get("assets"):
        merged = {"assets": [], "modules": []}
        for child in data["children"]:
            merged["assets"] += child.get("assets", [])
            merged["modules"] += child.get("modules", [])
        data = merged
    assets = [a for a in data.get("assets", []) if str(a.get("name", "")).endswith(".js")]
    for a in sorted(assets, key=lambda a: -a.get("size", 0)):
        kb = a.get("size", 0) / 1000
        if kb >= chunk_kb * 3:
            out.append(
                finding(
                    "medium",
                    "PERF003",
                    src,
                    0,
                    f"asset {a['name']} is {kb:.0f} kB (minified, before gzip)",
                    "split it: dynamic import() for rarely used code",
                )
            )
    pkg_size: dict[str, float] = {}
    pkg_paths: dict[str, set] = {}
    modules = data.get("modules", [])
    stack = list(modules)
    while stack:
        mod = stack.pop()
        stack += mod.get("modules", []) or []
        name = str(mod.get("name") or mod.get("identifier") or "")
        pkg = package_of(name)
        if not pkg:
            continue
        pkg_size[pkg] = pkg_size.get(pkg, 0) + (mod.get("size") or 0) / 1000
        root = name.replace("\\", "/").split(f"node_modules/{pkg}/")[0]
        pkg_paths.setdefault(pkg, set()).add(root)
    for pkg, kb in sorted(pkg_size.items(), key=lambda kv: -kv[1]):
        base = pkg.split("/")[0] if not pkg.startswith("@") else pkg
        for heavy, alt in HEAVY.items():
            if heavy in (pkg, base):
                out.append(
                    finding(
                        "medium" if kb > 30 else "low",
                        "PERF004",
                        src,
                        0,
                        f"heavy package {pkg} in the client bundle ({kb:.0f} kB parsed)",
                        alt,
                    )
                )
    for pkg, roots in sorted(pkg_paths.items()):
        if len(roots) > 1:
            out.append(
                finding(
                    "low",
                    "PERF005",
                    src,
                    0,
                    f"package {pkg} is bundled from {len(roots)} different node_modules paths",
                    "dedupe versions (npm dedupe / pnpm overrides) so one copy ships",
                )
            )
    top = sorted(pkg_size.items(), key=lambda kv: -kv[1])[:15]
    return out, {"top_packages_kb": {k: round(v, 1) for k, v in top}}


def gz_kb(path: Path) -> tuple[float, float]:
    data = path.read_bytes()
    return len(data) / 1000, len(gzip.compress(data, 9)) / 1000


def analyze_next_dir(next_dir: Path, warn_kb: float, fail_kb: float, chunk_kb: float) -> tuple[list[dict], dict]:
    out = []
    static = next_dir / "static"
    if not static.is_dir():
        return [finding("high", "PERF000", str(next_dir), 0, "no static/ folder: run next build first")], {}
    sizes: dict[str, tuple[float, float]] = {}
    for path in sorted(static.rglob("*.js")):
        sizes[path.relative_to(next_dir).as_posix()] = gz_kb(path)
    for name, (raw, gz) in sorted(sizes.items(), key=lambda kv: -kv[1][1]):
        if gz >= chunk_kb:
            out.append(
                finding(
                    "medium" if gz < chunk_kb * 2 else "high",
                    "PERF006",
                    name,
                    0,
                    f"chunk is {gz:.0f} kB gzip ({raw:.0f} kB raw)",
                    "find what is inside with `next analyze` (Turbopack, 16.1+) or @next/bundle-analyzer "
                    "(webpack), then lazy-load or replace it",
                )
            )
    routes = []
    manifests = [next_dir / "app-build-manifest.json", next_dir / "build-manifest.json"]
    for mf in manifests:
        if not mf.is_file():
            continue
        try:
            data = json.loads(mf.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        common = data.get("rootMainFiles", []) + data.get("polyfillFiles", [])
        for route, files in (data.get("pages") or {}).items():
            files = sorted(set(files + common))
            gz = sum(sizes.get(f, (0, 0))[1] for f in files if f.endswith(".js"))
            if gz:
                routes.append({"route": route, "first_load_kb": round(gz, 1), "files": len(files)})
    for r in routes:
        if r["first_load_kb"] >= warn_kb:
            out.append(
                finding(
                    "high" if r["first_load_kb"] >= fail_kb else "medium",
                    "PERF001",
                    r["route"],
                    0,
                    f"route {r['route']} ships about {r['first_load_kb']:.0f} kB gzip JS (budget {warn_kb:.0f} kB)",
                    "lazy-load below-the-fold client components and keep heavy libraries on the server",
                )
            )
    total_gz = sum(gz for _, gz in sizes.values())
    return out, {"chunks": len(sizes), "total_gzip_kb": round(total_gz, 1), "routes": routes}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Flag large routes, chunks and heavy packages in a Next.js build.")
    p.add_argument("--build-log", type=Path, help="saved `next build` output (Next.js 13-15)")
    p.add_argument("--stats", type=Path, help="webpack stats JSON")
    p.add_argument("--next-dir", type=Path, help="built .next directory")
    p.add_argument("--warn-kb", type=float, default=170.0, help="first-load JS budget per route (default 170)")
    p.add_argument("--fail-kb", type=float, default=300.0, help="first-load JS that counts as high (default 300)")
    p.add_argument("--chunk-kb", type=float, default=100.0, help="single chunk gzip size to flag (default 100)")
    p.add_argument("--json", action="store_true", help="print JSON (includes measured data)")
    p.add_argument("--fail-on", choices=SEVERITIES, default="medium", help="exit 1 at this severity")
    args = p.parse_args(argv)
    if not (args.build_log or args.stats or args.next_dir):
        p.error("give --build-log, --stats or --next-dir")
    findings: list[dict] = []
    data: dict = {}
    try:
        if args.build_log:
            parsed = parse_build_log(args.build_log.read_text(encoding="utf-8", errors="replace"))
            if not parsed["routes"]:
                print(
                    "error: no route sizes found (Next.js 16 removed sizes from `next build`; use --next-dir)",
                    file=sys.stderr,
                )
                return 2
            data["build_log"] = parsed
            findings += check_routes(
                parsed["routes"], parsed["shared_kb"], args.warn_kb, args.fail_kb, str(args.build_log)
            )
        if args.stats:
            stats = json.loads(args.stats.read_text(encoding="utf-8"))
            f, d = analyze_stats(stats, args.chunk_kb, str(args.stats))
            findings += f
            data["stats"] = d
        if args.next_dir:
            if not args.next_dir.is_dir():
                print(f"error: {args.next_dir} is not a directory", file=sys.stderr)
                return 2
            f, d = analyze_next_dir(args.next_dir, args.warn_kb, args.fail_kb, args.chunk_kb)
            findings += f
            data["next_dir"] = d
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        findings_sorted = sorted(findings, key=lambda f: -SEVERITIES.index(f["severity"]))
        print(json.dumps({"data": data, "findings": findings_sorted}, indent=2))
        threshold = SEVERITIES.index(args.fail_on)
        return 1 if any(SEVERITIES.index(f["severity"]) >= threshold for f in findings) else 0
    if "next_dir" in data:
        d = data["next_dir"]
        print(f"{d.get('chunks', 0)} chunks, {d.get('total_gzip_kb', 0)} kB gzip total")
        for r in sorted(d.get("routes", []), key=lambda r: -r["first_load_kb"])[:10]:
            print(f"  {r['first_load_kb']:>7.1f} kB  {r['route']}")
    if "stats" in data:
        print("largest packages (parsed kB):")
        for k, v in list(data["stats"]["top_packages_kb"].items())[:10]:
            print(f"  {v:>7.1f}  {k}")
    return emit(findings, args, "bundle report")


if __name__ == "__main__":
    sys.exit(main())
