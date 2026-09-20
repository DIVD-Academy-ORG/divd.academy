#!/usr/bin/env python3
"""Quality gate for the static site.

Checks every HTML page in the repository for:
- internal links and asset references that point to a file that does not exist
- required <head> metadata on content pages (title, description, canonical,
  hreflang, Open Graph image) - redirect stubs and 404.html are exempt
- the GoatCounter analytics snippet
- duplicated analytics snippets and obviously malformed URLs (`https://https://`)
- media rules from issue #17: every <img> has alt plus width/height, footer images are
  lazy-loaded and above-the-fold images are not
- structured data from issue #34: every JSON-LD block parses, uses absolute URLs and has
  sequential BreadcrumbList positions

Exit code 1 when a problem is found, so it can run in CI.

Usage: python3 scripts/check_site.py
"""
from __future__ import annotations

import json
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


IMG_RE = re.compile(r"<img\b[^>]*>", re.I)
JSONLD_RE = re.compile(
    r'<script type="application/ld\+json">(.*?)</script>', re.S | re.I
)


def check_media(page: Path, html: str, errors: list[str]) -> None:
    """Media pipeline rules (issue #17)."""
    rel = page.relative_to(ROOT)
    if is_stub(html):
        return
    body = html.split("<body", 1)[-1]
    footer = body.split("<footer", 1)[1] if "<footer" in body else ""
    for tag in IMG_RE.findall(body):
        if 'alt="' not in tag:
            errors.append(f"{rel}: <img> without alt attribute: {tag[:80]}")
        if not ('width="' in tag and 'height="' in tag):
            errors.append(f"{rel}: <img> without width/height: {tag[:80]}")
        in_footer = tag in footer
        lazy = 'loading="lazy"' in tag
        if in_footer and not lazy:
            errors.append(f"{rel}: footer <img> should be lazy-loaded: {tag[:80]}")
        if not in_footer and lazy:
            errors.append(f"{rel}: above-the-fold <img> must not be lazy-loaded: {tag[:80]}")


def check_structured_data(page: Path, html: str, errors: list[str]) -> None:
    """Structured data must be valid JSON with an absolute production URL (issue #34)."""
    rel = page.relative_to(ROOT)
    for raw in JSONLD_RE.findall(html):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            errors.append(f"{rel}: invalid JSON-LD ({exc.msg} at line {exc.lineno})")
            continue
        for match in re.findall(r'"(?:url|item|logo|image)":\s*"([^"]+)"', raw):
            if not match.startswith(("https://", "mailto:")):
                errors.append(f"{rel}: JSON-LD URL is not absolute: {match}")
        if isinstance(data, dict) and data.get("@type") == "BreadcrumbList":
            items = data.get("itemListElement", [])
            positions = [item.get("position") for item in items]
            if positions != list(range(1, len(items) + 1)):
                errors.append(f"{rel}: BreadcrumbList positions are not sequential")


def main() -> int:
    errors: list[str] = []
    checked = pages()
    for page in checked:
        html = page.read_text(encoding="utf-8", errors="replace")
        check_links(page, html, errors)
        check_meta(page, html, errors)
        check_analytics(page, html, errors)
        check_media(page, html, errors)
        check_structured_data(page, html, errors)

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
