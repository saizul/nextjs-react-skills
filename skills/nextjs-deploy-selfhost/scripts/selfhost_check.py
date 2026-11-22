#!/usr/bin/env python3
"""Check a Next.js project's self-hosting setup: next.config, Dockerfile, .dockerignore, nginx.

  next.config  output 'standalone' when a Dockerfile exists; features that break with
               output 'export'; images.domains / wildcard remotePatterns; multi-instance
               settings (--instances N): cacheHandler(s), deploymentId, encryption key
  Dockerfile   Node.js >= 20.9 base image, pinned tag, multi-stage, standalone copy of
               .next/static and public, HOSTNAME=0.0.0.0, non-root USER, node server.js
  .dockerignore  exists and excludes node_modules, .next, .git and .env files
  nginx        Host / X-Forwarded-* headers, buffering for streaming, caching of
               /_next/static, proxy_cache that ignores Cache-Control

Read-only, offline. Exit codes: 0 = nothing at or above --fail-on, 1 = findings, 2 = usage error.
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

CONFIG_NAMES = ("next.config.ts", "next.config.mjs", "next.config.js", "next.config.cjs")


def load_config(root: Path) -> tuple[str, str]:
    for name in CONFIG_NAMES:
        if (root / name).is_file():
            return name, strip_comments(read_text(root / name))
    return "", ""


def check_config(root: Path, has_docker: bool, instances: int) -> list[dict]:
    out: list[dict] = []
    name, cfg = load_config(root)
    output = re.search(r"output\s*:\s*['\"](standalone|export)['\"]", cfg)
    mode = output.group(1) if output else None
    label = name or "next.config"
    if has_docker and mode not in ("standalone", "export"):
        out.append(
            finding(
                "high",
                "DEP001",
                label,
                0,
                "Dockerfile present but output is not 'standalone'",
                "output: 'standalone' in next.config (image shrinks from ~1 GB to ~150 MB; run node server.js)",
            )
        )
    if mode == "export":
        out += check_export(root)
    if re.search(r"\bdomains\s*:\s*\[", cfg) and "images" in cfg:
        out.append(finding("low", "DEP002", label, 0, "images.domains is deprecated", "use images.remotePatterns"))
    m = re.search(r"hostname\s*:\s*['\"]\*\*?['\"]", cfg)
    if m:
        out.append(
            finding(
                "medium",
                "DEP003",
                label,
                line_of(cfg, m.start()),
                "images.remotePatterns allows any hostname (your server becomes an open image proxy)",
                "list the exact hosts you load images from",
            )
        )
    if "poweredByHeader" not in cfg and name:
        out.append(
            finding("info", "DEP004", label, 0, "X-Powered-By: Next.js header is sent", "poweredByHeader: false")
        )
    if instances > 1:
        if not re.search(r"cacheHandlers?\s*:", cfg):
            out.append(
                finding(
                    "medium",
                    "DEP005",
                    label,
                    0,
                    f"{instances} instances without a shared cacheHandler: each has its own ISR/data cache",
                    "cacheHandler (ISR) / cacheHandlers ('use cache') backed by Redis; cacheMaxMemorySize: 0",
                )
            )
        if "deploymentId" not in cfg:
            out.append(
                finding(
                    "medium",
                    "DEP006",
                    label,
                    0,
                    "no deploymentId: rolling deploys can hit version skew",
                    "deploymentId: process.env.DEPLOYMENT_VERSION (and a stable generateBuildId)",
                )
            )
        env_text = "\n".join(read_text(p) for p in [root / "Dockerfile", *root.glob("*compose*.y*ml")] if p.is_file())
        if "NEXT_SERVER_ACTIONS_ENCRYPTION_KEY" not in env_text + cfg:
            out.append(
                finding(
                    "medium",
                    "DEP007",
                    label,
                    0,
                    "multiple instances need the same NEXT_SERVER_ACTIONS_ENCRYPTION_KEY at build time",
                    "openssl rand -base64 32, store it as a CI secret, pass it to next build",
                )
            )
    return out


def check_export(root: Path) -> list[dict]:
    out = []
    for path in iter_files(root):
        code = strip_comments(read_text(path))
        rp = rel(path, root)
        stem = path.name.split(".")[0]
        if directive(code) == "server" or re.search(r"['\"]use server['\"]", code):
            out.append(finding("high", "DEP010", rp, 0, "Server Actions do not work with output: 'export'"))
        if stem == "route" and re.search(r"export\s+(async\s+)?(function|const)\s+(POST|PUT|PATCH|DELETE)\b", code):
            out.append(finding("high", "DEP010", rp, 0, "mutating route handler cannot run with output: 'export'"))
        if stem in ("proxy", "middleware") and path.parent in (root, root / "src"):
            out.append(finding("high", "DEP010", rp, 0, f"{stem}.ts does not run with output: 'export'"))
        m = re.search(r"\b(cookies|headers)\s*\(\s*\)", code)
        if m and directive(code) != "client":
            out.append(
                finding(
                    "high",
                    "DEP010",
                    rp,
                    line_of(code, m.start()),
                    f"{m.group(1)}() needs a server; not available in a static export",
                )
            )
    _, cfg = load_config(root)
    if "unoptimized" not in cfg and "loader" not in cfg:
        uses_image = any("next/image" in read_text(p) for p in iter_files(root))
        if uses_image:
            out.append(
                finding(
                    "high",
                    "DEP011",
                    "next.config",
                    0,
                    "next/image with output: 'export' needs images.unoptimized or a loader",
                    "images: { unoptimized: true } or a custom loader",
                )
            )
    return out


def check_dockerfile(root: Path) -> list[dict]:
    path = root / "Dockerfile"
    if not path.is_file():
        return []
    text = read_text(path)
    out: list[dict] = []

    def add(sev, rule, msg, fix="", line=0):
        out.append(finding(sev, rule, "Dockerfile", line, msg, fix))

    froms = list(re.finditer(r"^\s*FROM\s+(\S+)", text, re.I | re.M))
    for m in froms:
        image = m.group(1)
        if not image.startswith("node"):
            continue
        tag = image.split(":", 1)[1] if ":" in image else "latest"
        ver = re.match(r"(\d+)(?:\.(\d+))?", tag)
        if tag in ("latest", "current", "lts") or not ver:
            add(
                "medium",
                "DEP020",
                f"unpinned base image {image}",
                "pin a major version: node:22-alpine",
                line_of(text, m.start()),
            )
        elif int(ver.group(1)) < 20 or (int(ver.group(1)) == 20 and ver.group(2) and int(ver.group(2)) < 9):
            add(
                "high",
                "DEP021",
                f"{image}: Next.js 16 needs Node.js 20.9 or newer",
                "node:22-alpine (or node:24-alpine)",
                line_of(text, m.start()),
            )
    if len(froms) < 2:
        add(
            "medium",
            "DEP022",
            "single-stage build ships dev dependencies and source",
            "deps -> builder -> runner stages",
        )
    standalone = ".next/standalone" in text
    if standalone:
        if not re.search(r"\.next/static\s+\S*\.next/static", text):
            add(
                "high",
                "DEP023",
                "standalone output copied without .next/static (all JS/CSS 404)",
                "COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static",
            )
        if not re.search(r"COPY\s+.*\bpublic\b", text):
            add(
                "medium",
                "DEP024",
                "public/ is not copied into the runner image",
                "COPY --from=builder /app/public ./public",
            )
        if not re.search(r"HOSTNAME\s*=?\s*['\"]?0\.0\.0\.0", text):
            add(
                "medium",
                "DEP025",
                "HOSTNAME not set to 0.0.0.0 (standalone server binds to the container hostname)",
                'ENV HOSTNAME="0.0.0.0"',
            )
        if re.search(r"CMD\s*\[?[^\n]*(npm|pnpm|yarn)[^\n]*start|next\s+start", text):
            add(
                "low",
                "DEP026",
                "standalone image started with next start / npm start",
                'CMD ["node", "server.js"]',
            )
    if not re.search(r"^\s*USER\s+(?!root\b|0\b)\S+", text, re.M | re.I):
        add(
            "medium",
            "DEP027",
            "container runs as root",
            "create a user (adduser -S nextjs -u 1001) and USER nextjs",
        )
    if not re.search(r"NODE_ENV\s*=?\s*['\"]?production", text):
        add("low", "DEP028", "NODE_ENV=production not set in the runner stage", "ENV NODE_ENV=production")
    ignore = root / ".dockerignore"
    copies_all = re.search(r"^\s*COPY\s+(--\S+\s+)*\.\s+\.", text, re.M)
    if not ignore.is_file():
        add(
            "high" if copies_all else "medium",
            "DEP029",
            "no .dockerignore"
            + (" and `COPY . .` sends node_modules, .git and .env files into the build" if copies_all else ""),
            "add .dockerignore: node_modules .next .git .env* !.env.example",
        )
    else:
        ig = read_text(ignore)
        for pat, sev in (("node_modules", "medium"), (".next", "low"), (".git", "low"), (".env", "high")):
            if not re.search(rf"^\s*/?{re.escape(pat)}", ig, re.M):
                add(
                    sev,
                    "DEP030",
                    f".dockerignore does not exclude {pat}",
                    f"add {pat}{'*' if pat == '.env' else ''}",
                )
    return out


def check_nginx(paths: list[Path], root: Path) -> list[dict]:
    out: list[dict] = []
    for path in paths:
        text = read_text(path)
        code = "\n".join(line.split("#", 1)[0] for line in text.splitlines())
        rp = rel(path, root)
        if "proxy_pass" not in code:
            continue

        def add(sev, rule, msg, fix="", _rp=rp):
            out.append(finding(sev, rule, _rp, 0, msg, fix))

        if not re.search(r"proxy_set_header\s+Host\s+\$(host|http_host)", code):
            add(
                "high",
                "DEP040",
                "no `proxy_set_header Host $host` (Server Actions fail the Origin/Host check)",
                "proxy_set_header Host $host;",
            )
        if not re.search(r"proxy_set_header\s+X-Forwarded-Proto", code):
            add(
                "medium",
                "DEP041",
                "X-Forwarded-Proto not forwarded (wrong scheme in redirects/auth callbacks)",
                "proxy_set_header X-Forwarded-Proto $scheme;",
            )
        if not re.search(r"proxy_set_header\s+X-Forwarded-For", code):
            add(
                "low",
                "DEP042",
                "X-Forwarded-For not forwarded (client IP lost for rate limits/logs)",
                "proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;",
            )
        if not re.search(r"proxy_buffering\s+off|X-Accel-Buffering", code):
            add(
                "low",
                "DEP043",
                "nginx buffers responses: streaming / Suspense fallbacks arrive all at once",
                "proxy_buffering off; in the app location (or send X-Accel-Buffering: no from next.config headers)",
            )
        if "/_next/static" not in code:
            add(
                "info",
                "DEP044",
                "no dedicated /_next/static location",
                'location /_next/static/ { proxy_pass ...; expires 1y; add_header Cache-Control "public, immutable"; }',
            )
        if re.search(r"proxy_ignore_headers[^;]*Cache-Control", code) and "proxy_cache " in code:
            add(
                "high",
                "DEP045",
                "proxy_cache ignores Cache-Control: private, per-user pages can be cached and served to others",
                "respect upstream Cache-Control; cache only /_next/static and /_next/image",
            )
        if re.search(r"proxy_http_version\s+1\.0", code):
            add(
                "low",
                "DEP046",
                "proxy_http_version 1.0 disables keepalive and chunked streaming",
                "proxy_http_version 1.1;",
            )
    return out


def find_nginx(root: Path) -> list[Path]:
    found = []
    for d in (root, root / "nginx", root / "deploy", root / "ops", root / "docker", root / "infra"):
        if d.is_dir():
            found += sorted(p for p in d.glob("*.conf") if p.is_file())
    return found


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Check a Next.js self-hosting setup (config, Docker, nginx).")
    p.add_argument("path", nargs="?", default=".", help="project root (default: .)")
    p.add_argument(
        "--nginx",
        type=Path,
        action="append",
        default=[],
        help="nginx config file (repeatable); default: *.conf in ., nginx/, deploy/",
    )
    p.add_argument("--instances", type=int, default=1, help="number of app instances behind the proxy (default 1)")
    p.add_argument("--json", action="store_true", help="print JSON")
    p.add_argument("--fail-on", choices=SEVERITIES, default="medium", help="exit 1 at this severity")
    args = p.parse_args(argv)
    root = Path(args.path)
    if not root.is_dir():
        print(f"error: {root} is not a directory", file=sys.stderr)
        return 2
    for n in args.nginx:
        if not n.is_file():
            print(f"error: {n} not found", file=sys.stderr)
            return 2
    has_docker = (root / "Dockerfile").is_file()
    findings = check_config(root, has_docker, args.instances)
    findings += check_dockerfile(root)
    findings += check_nginx(args.nginx or find_nginx(root), root)
    return emit(findings, args, "self-host check")


if __name__ == "__main__":
    sys.exit(main())
