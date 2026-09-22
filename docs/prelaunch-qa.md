# Pre-launch QA (issue #44)

Run: **2026-09-22** on branch `chore/prelaunch-qa`, based on `main` @ `0cf9aff`,
served locally with `python3 -m http.server` (no TLS, gzip or cache headers).
Rerun all of this after the DNS/HTTPS cutover (#45); the production-only items at
the bottom can only be tested then.

## 1. Automated evidence

| Check | Command | Scope | Result |
|---|---|---|---|
| Links, metadata, media, JSON-LD, sitemap coverage | `python3 scripts/check_site.py` | 56 HTML files | 0 problems |
| Lang, single title/H1, self-canonicals, reciprocal hreflang, language switch, redirect stubs, sitemap/robots/404, subdomain redirect map | `python3 scripts/check_launch.py` (new) | 41 content pages + 15 redirect stubs | 0 problems (10 before the fixes in this PR, see §3) |
| Breadcrumb structured data up to date | `python3 scripts/generate_structured_data.py --check` | 38 pages | up to date |
| Sitemap up to date | `python3 scripts/generate_sitemap.py` + `git diff sitemap.xml` | | no diff |
| Accessibility: axe-core WCAG 2.0/2.1/2.2 A+AA + best practice, one main/H1, skip link, lang, reduced motion, reflow | `python3 scripts/check_a11y.py` | 41 pages at 1280 px, 320 px and 200% zoom | 0 problems |
| No-JavaScript state | Playwright, JS disabled, 390 px | 41 pages | all return 200, H1 visible, content rendered |
| Redirect stubs actually land | Playwright, JS enabled | 15 stubs | every stub ends on its target in one hop (list below) |
| External links | `python3 scripts/check_launch.py --external` | 46 unique URLs | all reachable; see §2 |
| Lighthouse (lab) | see `docs/media-and-performance.md` | | 100/100/100 (perf/a11y/SEO) on 2026-09-20; production run after #45 |

### Redirect matrix (tested)

| Legacy path | Lands on |
|---|---|
| `/about.html` | `/about/` |
| `/about/partners/` | `/partners/` |
| `/about/projects/` | `/projects/` |
| `/careers/`, `/careers/traineeships/` | `/traineeships/` |
| `/careers/volunteer/` | `/volunteers/` |
| `/home.html`, `/blog.html`, `/news.html` | `/` (no successor page exists; deliberate) |
| `/stage/` | `/nl/stages/aanmelden/` |
| `/support/` | `/contact/` (**changed**, was a dead Freshdesk desk) |
| `/courses/ethical-hacker/` | NetAcad course page |
| `/courses/introduction-to-cybersecurity/` | NetAcad course page (**changed**: was skillsforall.com, which itself redirected to NetAcad) |
| `/enquete/` | Jotform survey 252544159393059 |
| `/events/codeweek/` | Jotform Meet & Code 2023 (see blockers) |

All stubs are `noindex`, have a visible fallback link, and use one target for the
meta refresh, JS redirect and canonical (checked by `check_launch.py`). GitHub
Pages cannot send HTTP 301s; that is why meta refresh is used as the documented fallback (#42).

## 2. External links allowlist

Reported by the scripted check but working in a real browser (Playwright,
2026-09-22), and therefore allowlisted in `scripts/check_launch.py`:

- `politie.nl`, `denhaag.nl`: 403 for scripts, 200 in a browser.
- `divdacademy.substack.com`: Cloudflare challenge for scripts.

Review this list each quarter.

## 3. Fixed in this PR

1. `/support/` redirected to `divd-academy.freshdesk.com`: **that helpdesk no
   longer exists** (Freshdesk "no helpdesk" page, HTTP 404). Now redirects to `/contact/`.
2. `www.divd.works` (used on `/projects/` and `/nl/projects/`) **does not resolve**
   (no DNS record); replaced with `https://divd.works/`.
3. Four external redirect stubs (two courses, enquete, codeweek) had no `noindex`,
   no `lang` and three of them had no visible fallback link: fixed.
4. Redirect map for the old subdomains sent `the.divd.academy/careers` to `/careers/`,
   which is itself a stub (a redirect chain). It now goes straight to `/traineeships/`.

## 4. Launch blockers and owners

| Blocker | Issue | Owner | Status |
|---|---|---|---|
| Privacy, security and external-form review | #40 | Mischa | open, delegated 2026-09-21 |
| Fact-check claims, partners, contact details: register in `docs/fact-check-register.md` | #6 | Victor / Alex | register ready, needs sign-off |
| `/contact/` has no contact details at all | #6 | Victor / Alex | decision needed |
| Home says "Free: access to all published courses", FAQ says "most" | #6 | Victor / Alex | decision needed |
| Meet & Code **2023** sign-up still linked via `/events/codeweek/` | #6 | Victor | remove or repoint |
| Redirects on people/the subdomains before DNS removal | #42 | Victor | map ready (`docs/redirects-people-subdomain.md`) |
| CI quality gates: workflow in `docs/ci/quality-gates.yml` must be moved to `.github/workflows/` | #39 | Victor | the GitHub App cannot push workflows |
| DNS/HTTPS cutover | #45 | Victor | open |
| Performance in production (Lighthouse ≥ 95, INP) | #38 | after #45 | lab results OK |
| Search Console, monitoring | #46 | after #45 | open |
| Asset library / editorial baseline | #10 | Victor + Alex | meeting 2026-09-23 |
| Audiences, journeys, conversion goals | #7 | Victor | open |

## 5. Explicitly waived

- Manual screen reader round, focus order in the mobile menu and 1.4.12 text spacing:
  **waived by Victor Gevers on 2026-09-21** (#37 closed). As a result, no WCAG 2.2 AA
  conformance statement is published; the wording is "tested with axe-core, no automated findings".

## 6. Only testable after cutover (#45)

- HTTPS, HSTS, certificate, `www` → apex redirect, HTTP → HTTPS.
- Real 404 status from GitHub Pages on the production domain.
- Lighthouse and Core Web Vitals on `https://divd.academy/` (#38).
- Submitting the sitemap to Search Console (#46).
- Rerun `check_launch.py --external` and the redirect matrix against production.
