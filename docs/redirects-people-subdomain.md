# Redirect map: people.divd.academy and the.divd.academy

Both subdomains are Google Sites exports that duplicate content now living on
divd.academy. Point them at the new pages and stop maintaining them separately.
The redirects themselves have to be set on the subdomain (Google Sites / DNS /
hosting) &mdash; they cannot be committed in this repository.

| Old URL | New URL |
| --- | --- |
| people.divd.academy/ | https://divd.academy/volunteers/ |
| people.divd.academy/onboarding | https://divd.academy/getting-started/ |
| people.divd.academy/about | https://divd.academy/about/ |
| people.divd.academy/about/projects | https://divd.academy/projects/ |
| people.divd.academy/about/partners | https://divd.academy/partners/ |
| people.divd.academy/support | https://divd.academy/contact/ |
| people.divd.academy/support/make-an-appointment | https://divd.academy/internships/support/ |
| the.divd.academy/careers | https://divd.academy/careers/ |
| the.divd.academy/careers/volunteer | https://divd.academy/volunteers/ |
| the.divd.academy/faq | https://divd.academy/faq/ |

Content errors found on the old pages while migrating (fixed in the new pages,
still live on the old ones until the redirects are in place):

- people/Partners: the ECP entry contains the ESET description verbatim.
- people/About and people/Support: empty pages.
- people/Home: broken sentence "You can schedule this meeting at your convenience via ."
  and two "upload it" links without a target.

The account-activation instructions from people/Onboarding are deliberately public
(students often have never used Slack or Google Workspace, and instructions that
only live inside Slack are useless before you can get into Slack): /getting-started/
and /nl/aan-de-slag/.

Deliberately **not** migrated to the public site (kept in the Slack canvas and
handbook.divd.academy): room numbers, secured-zone references, guest-network
account procedure, visitor pick-up route, camera surveillance details, internal
Slack channel IDs and personal handles.
