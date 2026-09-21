#!/usr/bin/env python3
"""Accessibility gate for divd.academy (issue #37, WCAG 2.2 AA).

Runs axe-core over every published HTML page at 1280px and 320px, and adds
structural checks axe cannot do: one <main>, one <h1>, a skip link, a lang
attribute, a prefers-reduced-motion rule and reflow (no horizontal scrolling
at 320 CSS pixels or 200% zoom).

Usage:
    python3 scripts/check_a11y.py            # audit, exit 1 on findings
    python3 scripts/check_a11y.py --json out.json

Requires: playwright (`pip install playwright && playwright install chromium`)
and network access on the first run to fetch axe-core into scripts/.cache/.
Automated checks cannot establish conformance; keep the manual checklist in
docs/accessibility-audit.md up to date.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
CACHE = ROOT / "scripts" / ".cache" / "axe.min.js"
AXE_URL = "https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.9.1/axe.min.js"
TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa", "best-practice"]
PORT = 8791
SKIP_DIRS = (".worktrees/", "node_modules/", ".git/")


def html_pages() -> list[str]:
    pages = []
    for path in sorted(ROOT.rglob("*.html")):
        rel = path.relative_to(ROOT).as_posix()
        if rel.startswith(SKIP_DIRS):
            continue
        if 'http-equiv="refresh"' in path.read_text(errors="ignore").replace("'", '"').lower():
            continue  # redirect stubs have no content to audit
        pages.append(rel)
    return pages


def axe_source() -> str:
    if not CACHE.exists():
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_bytes(urllib.request.urlopen(AXE_URL, timeout=30).read())
    return CACHE.read_text()


STRUCTURE_JS = """() => ({
  skip: (() => { const a = document.querySelector('a[href^="#"]');
                 return a ? a.textContent.trim() : null; })(),
  lang: document.documentElement.lang,
  main: document.querySelectorAll('main').length,
  h1: document.querySelectorAll('h1').length,
  overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
  motion: [...document.styleSheets].some(s => { try {
      return [...s.cssRules].some(r => r.conditionText && r.conditionText.includes('reduced-motion'));
    } catch (e) { return false; } })
})"""


def structural_findings(info: dict) -> list[str]:
    out = []
    if not info["skip"]:
        out.append("no skip link as first in-page anchor")
    if not info["lang"]:
        out.append("no lang attribute on <html>")
    if info["main"] != 1:
        out.append(f"{info['main']} <main> landmarks (expected 1)")
    if info["h1"] != 1:
        out.append(f"{info['h1']} <h1> elements (expected 1)")
    if info["overflow"] > 1:
        out.append(f"horizontal overflow of {info['overflow']}px (WCAG 1.4.10 reflow)")
    if not info["motion"]:
        out.append("no prefers-reduced-motion rule applies")
    return out


def run() -> dict:
    from playwright.sync_api import sync_playwright

    axe = axe_source()
    pages = html_pages()
    server = subprocess.Popen([sys.executable, "-m", "http.server", str(PORT)], cwd=ROOT,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)
    findings: dict[str, list[str]] = {}
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            for width, height, zoom in [(1280, 900, 1.0), (320, 640, 1.0), (640, 512, 2.0)]:
                ctx = browser.new_context(viewport={"width": width, "height": height})
                page = ctx.new_page()
                for rel in pages:
                    page.goto(f"http://localhost:{PORT}/{rel}", wait_until="load")
                    if zoom != 1.0:
                        page.evaluate("z => document.body.style.zoom = z", zoom)
                    page.wait_for_timeout(150)
                    key = f"{rel} @{width}px zoom{zoom:g}"
                    issues = structural_findings(page.evaluate(STRUCTURE_JS))
                    if zoom == 1.0:
                        page.add_script_tag(content=axe)
                        res = page.evaluate(
                            "async t => await axe.run(document, {runOnly:{type:'tag',values:t}})", TAGS)
                        issues += [f"axe {v['id']} ({v['impact']}, {len(v['nodes'])}x): {v['help']}"
                                   for v in res["violations"]]
                    if issues:
                        findings[key] = issues
                ctx.close()
            browser.close()
    finally:
        server.terminate()
    return {"pages": len(pages), "findings": findings}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="write the full result to this file")
    args = ap.parse_args()
    result = run()
    if args.json:
        pathlib.Path(args.json).write_text(json.dumps(result, indent=2))
    for key, issues in result["findings"].items():
        print(f"== {key}")
        for issue in issues:
            print(f"   - {issue}")
    print(f"checked {result['pages']} HTML pages at 1280px, 320px and 200% zoom")
    print(f"{sum(len(v) for v in result['findings'].values())} problem(s)")
    return 1 if result["findings"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
