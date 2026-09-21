# Accessibility audit — WCAG 2.2 AA (issue #37)

Date of this run: 2026-09-21. Tooling: axe-core 4.9.1 via Playwright/Chromium
151, local static server. Scope: all 41 content pages (EN + NL); the redirect
stubs contain only a meta refresh and are excluded.

Reproduce with:

```
python3 scripts/check_a11y.py --json a11y.json
```

## Automated result

| Check | Result |
|---|---|
| axe-core, tags `wcag2a/aa`, `wcag21a/aa`, `wcag22aa`, `best-practice`, at 1280px | 0 violations |
| same, at 320px | 0 violations |
| One `<main>`, one `<h1>`, `lang` on `<html>`, skip link on every page | pass |
| Reflow: no horizontal scrolling at 320 CSS px and at 200% zoom | pass (after the fixes below) |
| `prefers-reduced-motion` honoured | pass |

## Fixed in this change

1. **Reflow (1.4.10).** `.button` had `white-space: nowrap`, so a long label
   ("Ga naar het aanmeldformulier (Engels)") pushed the layout past the
   viewport at 320 px and at 200% zoom. Buttons now wrap and are centred;
   the compact header nav keeps its own `nowrap` rule.
2. **Reflow, long strings (1.4.10).** `overflow-wrap: break-word` on `body`
   so e-mail addresses and URLs in running text cannot force horizontal
   scrolling. `html { overflow-x: hidden }` remains only as a safety net —
   it hides symptoms, so the layout itself must fit.
3. **Focus not obscured (2.4.11, new in WCAG 2.2).** The site header is
   sticky. `scroll-padding-top` on `html` and `scroll-margin-top` on
   `:target` keep a focused or linked element clear of the header instead of
   underneath it.
4. **Regression gate.** `scripts/check_a11y.py` runs the whole audit and
   exits non-zero on any finding, ready to be wired into the CI workflow of
   issue #39.

## Still manual — automated tools cannot establish conformance

These remain open and need a human pass before we claim AA conformance:

- Screen reader run (agree on one combination, e.g. NVDA + Firefox or
  VoiceOver + Safari) over the primary journeys: home → courses → apply, and
  home → internships → contact, in EN and NL.
- Focus order and visible focus while actually tabbing, including the mobile
  menu button at 320 px.
- Text spacing override (1.4.12) and a 200% zoom reading pass by a human.
- External forms are out of our control: the application form is hosted by
  Jotform and the course platform by Thinkific. Their accessibility is not
  covered by this audit and should be recorded as a third-party dependency
  (see issue #40 for the privacy/security side of the same forms).
- 3.3.8 accessible authentication applies to those external platforms, not
  to this static site.
