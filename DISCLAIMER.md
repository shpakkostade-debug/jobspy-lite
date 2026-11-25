# Disclaimer

jobspy-lite is an independent open-source project. It is **not affiliated with, endorsed by,
or supported by** LinkedIn, Indeed, StepStone, the Bundesagentur für Arbeit (Arbeitsagentur),
or any of their parent or subsidiary companies. All product names, logos and trademarks are
the property of their respective owners and are used here only to describe what the software
connects to.

## Terms of service

The software retrieves publicly visible job listings from third-party websites and APIs. Those
sites have their own terms of service, robots policies and rate limits, and many of them
prohibit automated collection. **You are responsible for complying with them.** In particular:

- check the terms of service and `robots.txt` of every board you query before using this tool
  at any scale;
- do not use the tool to overload a service, to circumvent access controls, captchas or
  paywalls, or to republish scraped content as your own;
- keep request volume low (the defaults are deliberately conservative), use `--proxies`
  responsibly, and stop when a board answers `403`/`429` instead of retrying in a loop;
- if you need guaranteed, licensed access to job data, use the official partner APIs of the
  respective boards instead of this project.

## Personal data

Job listings can contain personal data (recruiter names, e-mail addresses, phone numbers).
If you store or process such data, you are the controller for the purposes of the GDPR and
similar laws. Do not use this software for automated decision-making about individuals,
profiling, or any processing that the data subject has not consented to or that has no other
lawful basis.

## No warranty

The software is provided "as is", without warranty of any kind, express or implied, including
but not limited to the warranties of merchantability, fitness for a particular purpose and
non-infringement. The authors are not liable for any claim, damages or other liability arising
from the use of the software or from data obtained with it.

Scrapers depend on page markup, private endpoints and anti-bot measures that change without
notice. Results may be incomplete, duplicated, out of date or wrong. Do not rely on them as
the sole source for decisions with financial, legal or employment consequences.

## Licence

The source code is released under the MIT License; see [`LICENSE`](LICENSE), which also
preserves the copyright notice of the upstream project this code derives from
(JobSpy 1.5.0, MIT, Cullen Watson and contributors).

Nothing in this document is legal advice. If your use case is regulated, consult a lawyer.
