#!/usr/bin/env python3
"""Generate sitemap.xml from the HTML files in this repository.

Rules:
- every `index.html` becomes a directory URL (`courses/index.html` -> `/courses/`)
- pages with `<meta name="robots" content="noindex">` or a meta refresh are skipped
- legacy Google Sites exports are skipped (see SKIP_PREFIXES)
- hreflang alternates are read from each page's own <link rel="alternate"> tags

Usage: python3 scripts/generate_sitemap.py  (writes sitemap.xml)
"""
from __future__ import annotations

import re
from pathlib import Path

BASE = "https://divd.academy"
ROOT = Path(__file__).resolve().parent.parent
SKIP_PREFIXES = (".worktrees/",)
SKIP_FILES = {"404.html"}
ALT_RE = re.compile(
    r'<link\s+rel="alternate"\s+hreflang="([^"]+)"\s+href="([^"]+)"', re.I
)


def page_url(rel: str) -> str:
    return f"{BASE}/" if rel == "index.html" else f"{BASE}/{rel[: -len('index.html')]}"


def collect() -> list[tuple[str, list[tuple[str, str]]]]:
    entries = []
    for path in sorted(ROOT.rglob("*.html")):
        rel = path.relative_to(ROOT).as_posix()
        if rel in SKIP_FILES or rel.startswith(SKIP_PREFIXES):
            continue
        if not rel.endswith("index.html"):
            continue
        html = path.read_text(encoding="utf-8", errors="replace")
        if re.search(r'name="robots"[^>]*noindex', html, re.I):
            continue
        if re.search(r'http-equiv="refresh"', html, re.I):  # redirect stub
            continue
        entries.append((page_url(rel), ALT_RE.findall(html)))
    return entries


def render(entries) -> str:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"',
        '        xmlns:xhtml="http://www.w3.org/1999/xhtml">',
    ]
    for loc, alts in entries:
        lines.append("  <url>")
        lines.append(f"    <loc>{loc}</loc>")
        for lang, href in alts:
            lines.append(
                f'    <xhtml:link rel="alternate" hreflang="{lang}" href="{href}"/>'
            )
        lines.append("  </url>")
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


def main() -> None:
    entries = collect()
    (ROOT / "sitemap.xml").write_text(render(entries), encoding="utf-8")
    print(f"sitemap.xml written with {len(entries)} URLs")


if __name__ == "__main__":
    main()
