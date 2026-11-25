# jobspy-lite

Search four job boards from a single command or a single Python call:
**Indeed**, **LinkedIn**, **Arbeitsagentur** (official JSON API) and **StepStone**.
No pandas, no numpy: the result is a list of pydantic models that is written to JSONL, JSON or CSV.

> Job scrapers for Indeed, LinkedIn, Arbeitsagentur and StepStone — a pandas-free fork of
> [JobSpy](https://github.com/speedyapply/JobSpy) 1.5.0.

## Why

- **One query, four boards.** Results are collected in parallel; one board failing does not take down the others.
- **Cheap descriptions.** Job pages are opened in a second pass, and only for records that survived filtering and deduplication.
- **Deduplication.** The same vacancy posted on LinkedIn, StepStone and Arbeitsagentur collapses into one record (`--dedupe`).
- **Light dependencies.** `requests`, `beautifulsoup4`, `markdownify`, `pydantic`, `curl_cffi` instead of pandas + numpy (~116 MB).
- **Pipeline friendly.** JSONL on stdout, stable exit codes, and counters for filtered and merged records on stderr.

## Boards

| Board | How | Jobs per page | Description | `--hours-old` |
|---|---|---|---|---|
| Indeed | GraphQL API | 100 | always included | yes |
| LinkedIn | guest HTML | 10 | `--fetch-description` | yes |
| Arbeitsagentur | public JSON API `/pc/v6/jobs` | 100 | `--fetch-description` (`/pc/v4/jobdetails/{base64(refnr)}`) | yes |
| StepStone | HTML via `curl_cffi` (Chrome TLS) | 25 | `--fetch-description` (JSON-LD) | no, emits a warning |

Descriptions are fetched in a second pass — only for vacancies that remain after filters and
deduplication (see "Processing order").

Arbeitsagentur does not publish salary amounts — only the type (`STUNDENLOHN`, `JAHRESGEHALT`) —
so its `min_amount`/`max_amount` are empty. StepStone reports a salary only when it is present
in the JSON-LD.

## Installation

Python 3.10+ is required.

```bash
# isolated, no manual venv
uv tool install "git+https://github.com/koztix/jobspy-lite"
pipx install "git+https://github.com/koztix/jobspy-lite"

# or into the current environment
pip install "git+https://github.com/koztix/jobspy-lite"
```

From source:

```bash
git clone https://github.com/koztix/jobspy-lite
cd jobspy-lite
python -m venv .venv
.venv/Scripts/python -m pip install -e .      # Linux/macOS: .venv/bin/python
```

After installation the `jobspy-lite` command is available (and the module `python -m jobspy_lite`).

The Arbeitsagentur key is public (`jobboerse-jobsuche`) and already built in; you can supply your
own with `--arbeitsagentur-api-key` or the `JOBSUCHE_API_KEY` environment variable.

## Quick start

```bash
# all four boards, 20 jobs from each, JSONL on stdout
jobspy-lite "Softwareentwickler" --location "Berlin, Germany" --country-indeed germany -n 20

# StepStone only, with descriptions and deduplication, written to a file
jobspy-lite "Data Engineer" --site stepstone --location München --dedupe --fetch-description -o jobs.jsonl

# Arbeitsagentur, last 24 hours
jobspy-lite "Erzieher" --site arbeitsagentur --hours-old 24

# only jobs whose title contains python or backend
jobspy-lite "Entwickler" --title-filter "python|backend" --fields title,company,job_url
```

## CLI

```
jobspy-lite [QUERY] [options]
```

### Search

| Flag | Meaning |
|---|---|
| `QUERY` | search term (positional) |
| `--location TEXT` | city, region or country |
| `--distance N` | radius in miles (default 50) |
| `--remote` | remote jobs only |
| `--job-type T` | `fulltime`, `parttime`, `contract`, `temporary`, `internship`, `perdiem`, `other`, `volunteer` |
| `--hours-old N` | posted within the last N hours (Indeed, LinkedIn, Arbeitsagentur) |
| `--easy-apply` | only jobs posted on the board itself |
| `--country-indeed C` | Indeed country (default `usa`); use `germany` for Germany |
| `-n`, `--results-wanted N` | how many jobs **per board** (default 5) |
| `--offset N` | skip the first N results |

### Boards and requests

| Flag | Meaning |
|---|---|
| `--site LIST` | `indeed,linkedin,arbeitsagentur,stepstone` (all four by default) |
| `--fetch-description` | open job pages — only for records that survived filters and `--dedupe` |
| `--description-format F` | `markdown` (default), `html`, `plain` |
| `--enforce-annual-salary` | convert salaries to an annual figure |
| `--linkedin-company-ids IDS` | restrict LinkedIn to a list of companies |
| `--arbeitsagentur-api-key KEY` | your own Arbeitsagentur key |
| `--stepstone-impersonate NAME` | browser fingerprint for StepStone (default `chrome`) |
| `--proxies LIST` | comma-separated proxies; rotated when several are given |
| `--ca-cert PATH` | CA bundle for proxies |
| `--user-agent TEXT` | override the User-Agent |

### Output

| Flag | Meaning |
|---|---|
| `--fields LIST` | `title,company,job_url` or `all`; a compact set by default |
| `--title-filter REGEX` | keep jobs whose title matches the regex (case-insensitive) |
| `--location-filter TEXT` | keep jobs whose location contains the substring |
| `--dedupe` | merge one vacancy found on several boards |
| `-o`, `--output PATH` | `.jsonl`, `.json` or `.csv` instead of stdout |
| `--verbose 0..2` | `0` — errors only, `2` — all logs |
| `--version` | package version |

### Output format

- stdout carries **JSON Lines**: one object per job, fields the board did not provide are omitted.
- `-o file.csv` always writes every column; `--fields` applies to JSONL/JSON and stdout.
- Counters (`N jobs filtered out`, `N duplicates merged`, `N jobs written to …`) go to **stderr**, so stdout stays clean JSONL.

Exit codes:

| Code | Meaning |
|---|---|
| `0` | at least one board responded — including when it returned zero jobs |
| `1` | every requested board failed (network, blocking) |
| `2` | invalid arguments (for example a bad regex in `--title-filter`) — before any network request |

## Processing order

```
collect results → --title-filter/--location-filter → --dedupe → --fetch-description
```

`--fetch-description` opens pages only for the surviving records: jobs dropped by a filter and
merged duplicates never cost a request. Indeed already includes the description in its results,
so the second pass skips it.

## Deduplication

The same vacancy is often posted on several boards at once. The `--dedupe` flag
(`dedupe=True` in Python) merges such records after collection:

- normalized title and company — without "(m/w/d)", legal forms
  (`GmbH`, `AG`, `SE`, `Co. KG`) and conjunctions (`und`, `&`);
- the employer's direct URL (`job_url_direct`) without its query string;
- title similarity (Jaccard ≥ 0.85) within the same company.

The record with the most complete set of fields is kept, empty fields are filled from the others,
and `emails` and `job_type` are combined. The number of merged records is printed to stderr and
exposed as `ScrapeResults.duplicates_removed`. The function is also available on its own:
`from jobspy_lite.dedupe import dedupe_jobs`.

## Filters

`--title-filter REGEX` keeps jobs whose title matches the regex (case-insensitive), and
`--location-filter TEXT` keeps those whose location contains the substring. The number of dropped
records is printed to stderr and exposed as `ScrapeResults.filtered_out`.
An invalid regex exits with code `2` without a single network request.

## Python API

`scrape_jobs()` returns a list of `JobPost` (pydantic models), not a DataFrame:

```python
from jobspy_lite import scrape_jobs

results = scrape_jobs(
    site_name=["indeed", "linkedin", "arbeitsagentur", "stepstone"],
    search_term="Softwareentwickler",
    location="Berlin, Germany",
    country_indeed="germany",
    results_wanted=20,
    fetch_description=True,
)
for job in results:
    print(job.site, job.title, job.company, job.job_url)

print(results.errors)    # {site: message} — boards that did not respond
print(results.warnings)  # {site: [messages]}
print(results.filtered_out, results.duplicates_removed)
```

Calling a single scraper directly:

```python
from jobspy_lite.stepstone import StepStone
from jobspy_lite.model import ScraperInput

scraper = StepStone()
jobs = scraper.scrape(ScraperInput(search_term="Python", location="Berlin"))
jobs = [scraper.enrich(job) for job in jobs]   # descriptions, if needed
```

## Limitations

- **LinkedIn** — guest search: up to 1000 results, and it answers `403`/`429` under frequent requests.
  There are no retries (same as upstream JobSpy); when blocked you need a proxy or a pause.
  `--remote` and `--job-type` are not supported — a warning is emitted.
- **StepStone** — no time filter; the parser depends on the page markup and on the `curl_cffi`
  TLS fingerprint, so it can break when the site changes.
- **Arbeitsagentur** — salary amounts are not published; the public key is rate limited.
- **Indeed** — for non-US results you must pass `--country-indeed`.
- Read-only: signing in, applying and captcha bypass are not supported.
- Boards change their markup and rules; without warnings the parsers make no stability guarantees.

## Troubleshooting

| Symptom | Cause and what to do |
|---|---|
| `response status code 429 (blocked: use a proxy)` | the board rate-limited your IP; wait, lower `-n`, set `--proxies`. Do not retry in a loop |
| `exit 1`, all boards in `errors` | no network, DNS failure or the boards are blocked; test a single board with `--site` |
| `exit 2` | argument error, for example the regex in `--title-filter`; no network is touched |
| Cyrillic breaks in a Windows console | set `PYTHONIOENCODING=utf-8` |
| "0 jobs" but exit code `0` | the boards responded, they simply found nothing; check `--country-indeed` and `--location` |
| StepStone returned nothing | try `--stepstone-impersonate chrome124` or another fingerprint |

## Development

```bash
python -m pip install -e ".[dev]"
python -m pytest                  # 25 offline tests, no network needed
python -m build --outdir dist     # wheel and sdist
```

## License and provenance

The code is derived from JobSpy 1.5.0 (MIT, Cullen Watson and project contributors).
The license is MIT, see [`LICENSE`](LICENSE): it retains the JobSpy copyright notice.
The Indeed and LinkedIn parsers are unchanged; Arbeitsagentur and StepStone were added on top of
the same models.

## Disclaimer

This project is not affiliated with LinkedIn, Indeed, StepStone or the Bundesagentur für Arbeit.
Scraping may violate the terms of service of those boards; complying with their rules and with the
law is the user's responsibility. See [`DISCLAIMER.md`](DISCLAIMER.md) for details.

## Differences from JobSpy

- `scrape_jobs()` → `list[JobPost]`; `job.model_dump()` gives a flat dict (location as a string, enums as values).
- No `linkedin_fetch_description` (legacy alias) — use `fetch_description`.
- No `google_search_term` and no fields for boards that were removed.
- `JobPost` drops fields that only the removed parsers filled: `skills`, `experience_range`,
  `listing_type`, `vacancy_count`, `work_from_home_type`.
- Adds `--title-filter`, `--location-filter`, `--dedupe`, `--version` and description fetching
  after filtering.
