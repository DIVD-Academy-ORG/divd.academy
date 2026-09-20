# Media pipeline, progressive enhancement and performance budget

Covers issues `#17` (media pipeline & progressive enhancement) and `#38` (performance
budget & Core Web Vitals). The site is frameworkless static HTML on GitHub Pages; these
are the rules the pages follow and the measurements that back them up.

## Media rules

- Every `<img>` carries `width` and `height` matching the file's **intrinsic aspect
  ratio**, so no layout shift occurs while the image loads.
- The header logo is the likely LCP element: it is loaded eagerly with
  `fetchpriority="high"` and `decoding="async"`. It is never lazy-loaded.
- Footer and other below-the-fold images use `loading="lazy" decoding="async"`.
- Alt text describes the image's function (`alt="DIVD Academy"` for the logo link).
  Purely decorative images get `alt=""` and stay out of the accessibility tree.
- No production image ships at a substantially larger resolution than it is displayed
  at. The logo (570 × 161) is the single raster asset used on the pages and is stored
  palette-quantised (64 colours, 5.1 KB, visually identical to the 17.7 KB original).
- `picture`/`srcset` is only introduced once a page actually ships a photograph; today
  no content page does.

`scripts/check_site.py` enforces the alt/dimension/lazy rules on every page.

## Progressive enhancement

- All navigation links, cards and page content are present in the HTML. With JavaScript
  disabled, every page still shows its full main content and all 10 navigation links
  (verified with a JS-disabled browser context).
- `js/main.js` (1.5 KB) does one thing: toggle the mobile navigation and its
  `aria-expanded` state. No framework, no build step, no polyfills.
- The only third-party script is the GoatCounter counter, loaded `async`.

## Performance budget

| Budget | Target | Actual |
| --- | --- | --- |
| CSS shipped per page | ≤ 25 KB uncompressed | 18.2 KB (3 files) |
| Non-essential JS | ≤ 20 KB compressed | 1.5 KB own script + async GoatCounter |
| Requests per page | ≤ 10 | 7–8 |
| Total page weight | ≤ 120 KB | 55–60 KB |
| CLS | < 0.1 | 0.000–0.001 |

Unused legacy assets were removed in this pass (Bootstrap CSS/JS, Tailwind `output.css`,
`all.min.css`, `nav.css`, `foot.css`, `style.css`, `script.js`, three unused photographs
of 5.4 MB in total, and the 1.6 MB Jotform vendor bundle under `join/` — including
jQuery 1.8, which was unmaintained and a standing security liability). No page referenced
any of them.

## Measurements

Lab measurements, taken 2026-09-20 on the branch
`feat/structured-data-media-performance`:

- **Tooling:** Lighthouse 12.8.2, headless Chromium 1234 (Playwright build), pages served
  from a local `python3 -m http.server` at `127.0.0.1`.
- **Pages:** `/`, `/nl/`, `/courses/`, `/nl/stages/`, plus `/internships/`,
  `/getting-started/`, `/faq/` for weight and no-JS checks.

| Page | Preset | Performance | Accessibility | SEO | LCP | CLS |
| --- | --- | --- | --- | --- | --- | --- |
| `/` | desktop | 100 | 100 | 100 | 0.4 s | 0 |
| `/nl/` | desktop | 100 | 100 | 100 | 0.4 s | 0.001 |
| `/courses/` | desktop | 100 | 100 | 100 | 0.4 s | 0 |
| `/nl/stages/` | desktop | 100 | 100 | 100 | 0.4 s | 0 |
| `/` | mobile | 100 | 100 | — | 1.4 s | 0 |
| `/nl/stages/` | mobile | 100 | 100 | — | 1.4 s | 0 |

**Read these as diagnostics, not field guarantees.** A localhost origin has no network
latency, no TLS handshake, no gzip and no cache headers, so the remaining Lighthouse
best-practices findings (`is-on-https`, `uses-text-compression`, `uses-long-cache-ttl`,
`unminified-css`) are artefacts of the test server: GitHub Pages serves the site over
HTTPS with compression and caching. INP has no lab equivalent and needs field data.

Repeat after the production cutover (`#45`) against `https://divd.academy/` and record
the numbers here; only then can the "Lighthouse ≥ 95 in production" criterion of `#38`
be ticked off.
