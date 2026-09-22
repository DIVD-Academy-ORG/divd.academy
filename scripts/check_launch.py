#!/usr/bin/env python3
"""Pre-launch checks for divd.academy (issues #39, #42 and #44).

Static, stdlib-only checks that complement scripts/check_site.py (links, metadata,
media, JSON-LD) and scripts/check_a11y.py (axe-core, needs a browser):

content pages
- <html lang> is set and matches the language of the path (/nl/... = nl)
- exactly one non-empty <title> and exactly one <h1>
- the canonical is absolute, on https://divd.academy and equals the page's own URL
- hreflang alternates are absolute, include x-default, point to existing content
  pages and are reciprocal (the NL page points back to the EN page and vice versa)
- the EN/NL switch in the header links to the hreflang counterpart

redirect stubs (meta refresh pages, issue #42)
- meta refresh, JS redirect, canonical and visible fallback link agree on one target
- the target exists and is not itself a redirect stub (no redirect chains)
- the stub is noindex

site files
- every sitemap <loc> and xhtml:link maps to an existing content page (no stubs,
  no noindex pages), robots.txt references the sitemap, 404.html is noindex
- the legacy-subdomain map in docs/redirects-people-subdomain.md only targets
  final destinations (no stub in between)

Optional: --external performs a HEAD/GET request per unique external link and
reports non-2xx/3xx answers. External results are reported, never fatal, because
third-party sites fail intermittently (see docs/prelaunch-qa.md for the allowlist).

Exit code 1 on any internal finding, so it can run in CI.

Usage:
    python3 scripts/check_launch.py
    python3 scripts/check_launch.py --external
"""
from __future__ import annotations

import argparse
import html as htmllib
import concurrent.futures
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://divd.academy"
SKIP_DIRS = (".git", ".worktrees", "node_modules", ".cache")
EXTERNAL_ALLOWLIST = (
    # sites that block scripted requests but work in a browser
    "linkedin.com",
    "x.com",
    "twitter.com",
    "politie.nl",  # 403 for scripts, 200 in a real browser [2026-09-22]
    "denhaag.nl",  # idem
    "substack.com",  # Cloudflare challenge for scripts
)


def pages() -> list[Path]:
    return [
        p
        for p in sorted(ROOT.rglob("*.html"))
        if not any(part in SKIP_DIRS for part in p.relative_to(ROOT).parts)
    ]


def rel(page: Path) -> str:
    return page.relative_to(ROOT).as_posix()


def url_of(page: Path) -> str:
    r = rel(page)
    if r.endswith("index.html"):
        return f"{BASE}/{r[: -len('index.html')]}"
    return f"{BASE}/{r}"


def page_for(url: str) -> Path | None:
    if url.startswith(BASE):
        url = url[len(BASE):]
    if not url.startswith("/"):
        return None
    path = url.split("#")[0].split("?")[0]
    candidate = ROOT / path.lstrip("/")
    if path.endswith("/") or candidate.is_dir():
        candidate = candidate / "index.html"
    return candidate if candidate.exists() else None


def is_stub(html: str) -> bool:
    return bool(re.search(r'http-equiv="refresh"', html, re.I))


def is_noindex(html: str) -> bool:
    return bool(re.search(r'name="robots"[^>]*noindex', html, re.I))


def attr(pattern: str, html: str) -> list[str]:
    return re.findall(pattern, html, re.I | re.S)


def check_content_page(page: Path, html: str, errors: list[str]) -> None:
    r = rel(page)
    lang = attr(r'<html[^>]*\blang="([^"]*)"', html)
    expected = "nl" if r.startswith("nl/") else "en"
    if not lang or not lang[0]:
        errors.append(f"{r}: <html> has no lang attribute")
    elif lang[0].split("-")[0].lower() != expected:
        errors.append(f"{r}: lang=\"{lang[0]}\" but path implies {expected}")

    titles = [t.strip() for t in attr(r"<title>(.*?)</title>", html)]
    if len(titles) != 1 or not titles[0]:
        errors.append(f"{r}: expected exactly one non-empty <title>, found {len(titles)}")
    h1 = attr(r"<h1\b", html)
    if len(h1) != 1:
        errors.append(f"{r}: expected exactly one <h1>, found {len(h1)}")

    if r == "404.html":
        return

    canon = attr(r'<link rel="canonical" href="([^"]+)"', html)
    if len(canon) != 1:
        errors.append(f"{r}: expected one canonical, found {len(canon)}")
    elif canon[0] != url_of(page):
        errors.append(f"{r}: canonical {canon[0]} != own URL {url_of(page)}")

    alts = dict(
        (h.lower(), u)
        for h, u in attr(r'<link rel="alternate" hreflang="([^"]+)" href="([^"]+)"', html)
    )
    if "x-default" not in alts:
        errors.append(f"{r}: hreflang x-default missing")
    for hl, target in alts.items():
        if not target.startswith(BASE + "/"):
            errors.append(f"{r}: hreflang {hl} is not absolute on {BASE}: {target}")
            continue
        tp = page_for(target)
        if tp is None:
            errors.append(f"{r}: hreflang {hl} target does not exist: {target}")
            continue
        thtml = tp.read_text(encoding="utf-8", errors="replace")
        if is_stub(thtml):
            errors.append(f"{r}: hreflang {hl} points to a redirect stub: {target}")
            continue
        if hl in ("en", "nl") and tp != page:
            back = dict(
                (h.lower(), u)
                for h, u in attr(
                    r'<link rel="alternate" hreflang="([^"]+)" href="([^"]+)"', thtml
                )
            )
            own_lang = expected
            if back.get(own_lang) != url_of(page):
                errors.append(
                    f"{r}: hreflang {hl} -> {target} is not reciprocal "
                    f"(that page's {own_lang} alternate is {back.get(own_lang)})"
                )

    other = "en" if expected == "nl" else "nl"
    switch = attr(rf'<a href="([^"]+)"[^>]*\bhreflang="{other}"', html)
    if switch and other in alts:
        target = switch[0] if switch[0].startswith("http") else BASE + switch[0]
        if target != alts[other]:
            errors.append(
                f"{r}: language switch goes to {switch[0]} but hreflang {other} is {alts[other]}"
            )


def stub_target(html: str) -> str | None:
    m = re.search(r'http-equiv="refresh"\s+content="\d+;\s*url=([^"]+)"', html, re.I)
    return m.group(1).strip() if m else None


def check_stub(page: Path, html: str, errors: list[str]) -> None:
    r = rel(page)
    target = stub_target(html)
    if not target:
        errors.append(f"{r}: redirect stub without a parseable meta refresh target")
        return
    if not is_noindex(html):
        errors.append(f"{r}: redirect stub is not noindex")
    body = html.split("<body", 1)[-1]
    links = attr(r'<a href="([^"]+)"', body)
    if not links:
        errors.append(f"{r}: redirect stub has no visible fallback link")
    def norm(u: str) -> str:
        u = htmllib.unescape(u).strip("'")
        return u[len(BASE):] if u.startswith(BASE) else u
    if links and norm(links[0]) != norm(target):
        errors.append(f"{r}: fallback link {links[0]} != refresh target {target}")
    js = attr(r'location\.replace\("([^"]+)"\)', html)
    if js and norm(js[0]) != norm(target):
        errors.append(f"{r}: JS redirect {js[0]} != refresh target {target}")
    canon = attr(r'<link rel="canonical" href="([^"]+)"', html)
    if target.startswith(("/", BASE)):
        if canon and norm(canon[0]) != norm(target):
            errors.append(f"{r}: canonical {canon[0]} != refresh target {target}")
        tp = page_for(target)
        if tp is None:
            errors.append(f"{r}: redirect target does not exist: {target}")
        elif is_stub(tp.read_text(encoding="utf-8", errors="replace")):
            errors.append(f"{r}: redirect chain {target} is itself a stub")


def check_site_files(errors: list[str]) -> None:
    sitemap = ROOT / "sitemap.xml"
    text = sitemap.read_text() if sitemap.exists() else ""
    if not text:
        errors.append("sitemap.xml missing")
    for url in set(re.findall(r"<loc>([^<]+)</loc>", text)) | set(
        re.findall(r'<xhtml:link[^>]*href="([^"]+)"', text)
    ):
        tp = page_for(url)
        if tp is None:
            errors.append(f"sitemap.xml: {url} does not exist")
            continue
        h = tp.read_text(encoding="utf-8", errors="replace")
        if is_stub(h) or is_noindex(h):
            errors.append(f"sitemap.xml: {url} is a stub or noindex page")

    robots = (ROOT / "robots.txt").read_text() if (ROOT / "robots.txt").exists() else ""
    if f"Sitemap: {BASE}/sitemap.xml" not in robots:
        errors.append("robots.txt: missing Sitemap line")
    if re.search(r"^Disallow:\s*/\s*$", robots, re.M):
        errors.append("robots.txt: disallows the whole site")

    nf = ROOT / "404.html"
    if not nf.exists() or not is_noindex(nf.read_text()):
        errors.append("404.html: missing or not noindex")

    rmap = ROOT / "docs" / "redirects-people-subdomain.md"
    if rmap.exists():
        for old, new in re.findall(r"^\| (\S+\.divd\.academy\S*) \| (https://\S+) \|", rmap.read_text(), re.M):
            tp = page_for(new)
            if tp is None:
                errors.append(f"redirect map: {old} -> {new} does not exist")
            elif is_stub(tp.read_text(encoding="utf-8", errors="replace")):
                errors.append(f"redirect map: {old} -> {new} is a stub (redirect chain)")


def external_links() -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for page in pages():
        html = page.read_text(encoding="utf-8", errors="replace")
        for u in re.findall(r'(?:href|src)="(https?://[^"]+)"', html):
            if u.startswith(BASE):
                continue
            found.setdefault(u, []).append(rel(page))
    return found


def probe(url: str) -> tuple[str, str]:
    headers = {"User-Agent": "Mozilla/5.0 (divd.academy link check)"}
    for method in ("HEAD", "GET"):
        try:
            req = urllib.request.Request(url, method=method, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                return url, str(resp.status)
        except urllib.error.HTTPError as exc:
            if method == "HEAD" and exc.code in (403, 405, 404, 400, 501):
                continue
            return url, str(exc.code)
        except Exception as exc:  # noqa: BLE001
            if method == "HEAD":
                continue
            return url, type(exc).__name__
    return url, "unknown"


def check_external() -> list[str]:
    found = external_links()
    report = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
        for url, status in ex.map(probe, sorted(found)):
            if status.isdigit() and int(status) < 400:
                continue
            allow = any(a in url for a in EXTERNAL_ALLOWLIST)
            tag = "ALLOWLISTED" if allow else "WARN"
            report.append(f"{tag} {status} {url} (on {', '.join(sorted(set(found[url]))[:3])})")
    print(f"checked {len(found)} unique external links")
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--external", action="store_true", help="also probe external links")
    args = ap.parse_args()

    errors: list[str] = []
    all_pages = pages()
    stubs = content = 0
    for page in all_pages:
        html = page.read_text(encoding="utf-8", errors="replace")
        if is_stub(html):
            stubs += 1
            check_stub(page, html, errors)
        else:
            content += 1
            check_content_page(page, html, errors)
    check_site_files(errors)

    print(f"checked {content} content pages and {stubs} redirect stubs")
    for e in errors:
        print(f"ERROR {e}")
    if args.external:
        for line in check_external():
            print(line)
    print(f"{len(errors)} problem(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
