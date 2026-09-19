#!/usr/bin/env python3
"""Quality gate for the static site.

Checks every HTML page in the repository for:
- internal links and asset references that point to a file that does not exist
- required <head> metadata on content pages (title, description, canonical,
  hreflang, Open Graph image) - redirect stubs and 404.html are exempt
- the GoatCounter analytics snippet
- duplicated analytics snippets and obviously malformed URLs (`https://https://`)

Exit code 1 when a problem is found, so it can run in CI.

Usage: python3 scripts/check_site.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = (".git", ".worktrees", "node_modules")
GOATCOUNTER = "divd-academy.goatcounter.com/count"
HREF_RE = re.compile(r'(?:href|src)="([^"#][^"]*)"')
EXEMPT_META = {"404.html"}


def pages() -> list[Path]:
    return [
        p
        for p in sorted(ROOT.rglob("*.html"))
        if not any(part in SKIP_DIRS for part in p.relative_to(ROOT).parts)
    ]


def is_stub(html: str) -> bool:
    return bool(re.search(r'http-equiv="refresh"', html, re.I))


def resolve(target: str, page: Path) -> Path | None:
    """Map an internal link to the file that should serve it."""
    path = target.split("?")[0].split("#")[0]
    if not path:
        return None
    base = ROOT if path.startswith("/") else page.parent
    candidate = (base / path.lstrip("/")).resolve()
    if candidate.is_dir() or path.endswith("/"):
        candidate = candidate / "index.html"
    return candidate


def check_links(page: Path, html: str, errors: list[str]) -> None:
    rel = page.relative_to(ROOT)
    for target in HREF_RE.findall(html):
        if re.match(r"^(https?:|mailto:|tel:|data:|//)", target):
            if target.startswith("https://https://") or "://https://" in target:
                errors.append(f"{rel}: malformed URL {target}")
            continue
        resolved = resolve(target, page)
        if resolved is not None and not resolved.exists():
            errors.append(f"{rel}: dead internal link {target}")


def check_meta(page: Path, html: str, errors: list[str]) -> None:
    rel = page.relative_to(ROOT)
    if rel.as_posix() in EXEMPT_META or is_stub(html):
        return
    required = {
        "title": r"<title>.+?</title>",
        "meta description": r'name="description"\s+content="[^"]+"',
        "canonical": r'rel="canonical"',
        "hreflang": r'rel="alternate"\s+hreflang=',
        "og:image": r'property="og:image"',
    }
    for label, pattern in required.items():
        if not re.search(pattern, html, re.S | re.I):
            errors.append(f"{rel}: missing {label}")


def check_analytics(page: Path, html: str, errors: list[str]) -> None:
    rel = page.relative_to(ROOT)
    count = html.count(GOATCOUNTER)
    if count == 0:
        errors.append(f"{rel}: missing GoatCounter snippet")
    elif count > 1:
        errors.append(f"{rel}: GoatCounter snippet appears {count} times")
    if "hs-scripts.com" in html:
        errors.append(f"{rel}: HubSpot tracker is back")


def main() -> int:
    errors: list[str] = []
    checked = pages()
    for page in checked:
        html = page.read_text(encoding="utf-8", errors="replace")
        check_links(page, html, errors)
        check_meta(page, html, errors)
        check_analytics(page, html, errors)

    sitemap = ROOT / "sitemap.xml"
    if sitemap.exists():
        listed = set(re.findall(r"<loc>([^<]+)</loc>", sitemap.read_text()))
        for page in checked:
            html = page.read_text(encoding="utf-8", errors="replace")
            if is_stub(html) or re.search(r'name="robots"[^>]*noindex', html, re.I):
                continue
            rel = page.relative_to(ROOT).as_posix()
            if rel == "404.html" or not rel.endswith("index.html"):
                continue
            url = "https://divd.academy/" + rel[: -len("index.html")]
            if url not in listed:
                errors.append(f"{rel}: not in sitemap.xml (run scripts/generate_sitemap.py)")

    print(f"checked {len(checked)} HTML files")
    for error in errors:
        print(f"ERROR {error}")
    print(f"{len(errors)} problem(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
