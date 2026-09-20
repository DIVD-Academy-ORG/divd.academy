#!/usr/bin/env python3
"""Generate BreadcrumbList JSON-LD for every content page (issue #34).

The site is static HTML, so the breadcrumb data is generated from the actual
directory structure and the visible <h1>/navigation labels of the pages
themselves. Nothing is invented: a crumb label is taken from the target page's
own <h1>, and a crumb is only emitted when the target page exists in the
repository.

The generated block is wrapped in markers so the script is idempotent:

    <!-- structured-data:breadcrumb -->
    <script type="application/ld+json"> ... </script>
    <!-- /structured-data:breadcrumb -->

Usage:
    python3 scripts/generate_structured_data.py           # write
    python3 scripts/generate_structured_data.py --check   # verify, exit 1 on drift
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = (".git", ".worktrees", "node_modules")
SITE = "https://divd.academy"
BEGIN = "  <!-- structured-data:breadcrumb -->"
END = "  <!-- /structured-data:breadcrumb -->"
BLOCK_RE = re.compile(
    r"[ \t]*<!-- structured-data:breadcrumb -->.*?<!-- /structured-data:breadcrumb -->\n",
    re.S,
)
H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.S | re.I)
TAG_RE = re.compile(r"<[^>]+>")
# Root pages act as the first crumb, so they get no breadcrumb of their own.
ROOTS = {"index.html", "nl/index.html"}
EXEMPT = {"404.html"}
ROOT_LABEL = {"": "DIVD Academy", "nl": "DIVD Academy"}


def pages() -> list[Path]:
    return [
        p
        for p in sorted(ROOT.rglob("*.html"))
        if not any(part in SKIP_DIRS for part in p.relative_to(ROOT).parts)
    ]


def is_stub(text: str) -> bool:
    return bool(re.search(r'http-equiv="refresh"', text, re.I))


def url_for(rel: str) -> str:
    """Canonical production URL for a repository-relative HTML path."""
    if rel.endswith("/index.html"):
        return f"{SITE}/{rel[: -len('index.html')]}"
    if rel == "index.html":
        return f"{SITE}/"
    return f"{SITE}/{rel}"


def heading(path: Path) -> str | None:
    match = H1_RE.search(path.read_text(encoding="utf-8"))
    if not match:
        return None
    text = html.unescape(TAG_RE.sub("", match.group(1)))
    return " ".join(text.split()) or None


def trail(rel: str) -> list[tuple[str, str]]:
    """[(name, url)] from the language root down to the page itself."""
    parts = rel.split("/")[:-1]  # drop index.html
    lang = "nl" if parts and parts[0] == "nl" else ""
    root_rel = "nl/index.html" if lang else "index.html"
    crumbs = [(ROOT_LABEL[lang], url_for(root_rel))]

    start = 1 if lang else 0
    for depth in range(start + 1, len(parts) + 1):
        ancestor = "/".join(parts[:depth])
        page = ROOT / ancestor / "index.html"
        if not page.exists():
            # No page for this path segment: it is not a navigable crumb.
            continue
        label = heading(page)
        if not label:
            continue
        crumbs.append((label, url_for(f"{ancestor}/index.html")))
    return crumbs


def block_for(crumbs: list[tuple[str, str]]) -> str:
    data = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i, "name": name, "item": url}
            for i, (name, url) in enumerate(crumbs, start=1)
        ],
    }
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    # JSON-LD must never contain a literal </script> or a raw < that could end
    # the script element early.
    payload = payload.replace("<", "\\u003c").replace(">", "\\u003e")
    body = "\n".join("  " + line for line in payload.splitlines())
    return (
        f"{BEGIN}\n"
        '  <script type="application/ld+json">\n'
        f"{body}\n"
        "  </script>\n"
        f"{END}\n"
    )


def apply(path: Path, block: str | None) -> bool:
    text = path.read_text(encoding="utf-8")
    stripped = BLOCK_RE.sub("", text)
    if block is None:
        new = stripped
    else:
        if "</head>" not in stripped:
            raise SystemExit(f"{path}: no </head> to insert before")
        new = stripped.replace("</head>", f"{block}</head>", 1)
    if new == text:
        return False
    path.write_text(new, encoding="utf-8")
    return True


def main() -> int:
    check = "--check" in sys.argv
    changed: list[str] = []
    for path in pages():
        rel = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8")
        skip = rel in ROOTS or rel in EXEMPT or is_stub(text) or "/" not in rel
        crumbs = [] if skip else trail(rel)
        block = block_for(crumbs) if len(crumbs) >= 2 else None

        current = BLOCK_RE.search(text)
        want = block or ""
        have = current.group(0) if current else ""
        if want == have:
            continue
        changed.append(rel)
        if not check:
            apply(path, block)

    if check:
        if changed:
            print("Breadcrumb data out of date on:")
            for rel in changed:
                print(f"  {rel}")
            return 1
        print("Breadcrumb structured data up to date.")
        return 0

    print(f"Updated breadcrumb structured data on {len(changed)} page(s).")
    for rel in changed:
        print(f"  {rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
