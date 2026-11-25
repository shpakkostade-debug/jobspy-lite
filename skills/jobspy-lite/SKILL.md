---
name: jobspy-lite
description: Use when the user wants to search job boards and get structured job data from the terminal or Python — Indeed, LinkedIn, Arbeitsagentur (Bundesagentur für Arbeit) and StepStone — e.g. "find backend jobs in Berlin", "collect vacancies into JSONL/CSV", "scrape Arbeitsagentur for the last 24 hours", "dedupe the same job across boards", or "fetch job descriptions". CLI is `jobspy-lite`; install with `uv tool install "git+https://github.com/shpakkostade-debug/jobspy-lite"`, `pipx install`, or `pip install`.
---

# jobspy-lite

A small Python package and CLI that searches four job boards and returns structured
listings: **Indeed**, **LinkedIn**, **Arbeitsagentur** and **StepStone**. It is a
pandas-free fork of [JobSpy](https://github.com/speedyapply/JobSpy) 1.5.0.
Python 3.10+.

## When to use this skill

Use it when the user wants to:

- search for vacancies by keyword and location and get them as data, not as a web page;
- collect listings into JSONL / JSON / CSV for later analysis or a pipeline;
- query the German public employment API (Arbeitsagentur) directly;
- merge the same vacancy found on several boards (`--dedupe`);
- filter results by title or location before fetching anything else;
- fetch full job descriptions for a small, already-filtered set of jobs.

**Do not use it** for logging in, applying to jobs, bypassing captchas, mass harvesting,
or anything requiring an official partner API. See the disclaimer at the end.

## Install

Prefer an isolated install so the CLI is on `PATH`:

```bash
uv tool install "git+https://github.com/shpakkostade-debug/jobspy-lite"
# or
pipx install "git+https://github.com/shpakkostade-debug/jobspy-lite"
# or into the current environment
pip install "git+https://github.com/shpakkostade-debug/jobspy-lite"
```

Verify: `jobspy-lite --version` (prints `jobspy-lite 0.1.0`).

From a checkout: `pip install -e ".[dev]"`, then `jobspy-lite --help`.
The Arbeitsagentur key is public and built in; no credentials are required for any board.

## Core commands

```bash
# all four boards, JSON Lines to stdout
jobspy-lite "Softwareentwickler" --location "Berlin, Germany" --country-indeed germany -n 20

# one board, deduplicated, with descriptions, to a file
jobspy-lite "Data Engineer" --site stepstone --location München --dedupe --fetch-description -o jobs.jsonl

# only jobs posted in the last 24 hours
jobspy-lite "Erzieher" --site arbeitsagentur --hours-old 24

# narrow before spending requests: title regex, then only a few fields
jobspy-lite "Entwickler" --title-filter "python|backend" --fields title,company,job_url,date_posted

# remote only, contract roles, CSV
jobspy-lite "product manager" --location Germany --remote --job-type contract -o jobs.csv
```

## Flags that matter

| Flag | Meaning |
|---|---|
| `QUERY` | positional search term |
| `--location TEXT` | city, region or country |
| `--site LIST` | comma list of `indeed,linkedin,arbeitsagentur,stepstone`; **omit for all four** |
| `-n N` | results **per board**, default 5 |
| `--hours-old N` | posted within N hours (Indeed, LinkedIn, Arbeitsagentur only) |
| `--country-indeed C` | Indeed country, default `usa`; German searches need `germany` |
| `--remote`, `--job-type T`, `--easy-apply`, `--offset N` | search filters |
| `--title-filter REGEX` | keep titles matching the regex (case-insensitive) |
| `--location-filter TEXT` | keep locations containing the text |
| `--dedupe` | merge the same job found on several boards |
| `--fetch-description` | open each surviving job page; `--description-format markdown\|html\|plain` |
| `--fields LIST` | `all` or comma list; affects JSONL/JSON and stdout |
| `-o PATH` | `.jsonl`, `.json` or `.csv` instead of stdout |
| `--proxies LIST` | comma list; rotated when several |
| `--verbose 0..2` | log level |

## Output contract

- stdout is **JSON Lines**, one object per job, fields a board did not provide are omitted.
- `-o file.csv` always writes every column; `--fields` only shapes JSONL/JSON/stdout.
- Counters (`N jobs filtered out`, `N duplicates merged`, `N jobs written to …`) go to **stderr**,
  so `jobspy-lite ... > jobs.jsonl` yields clean data.
- Exit codes: `0` — at least one board answered (even with zero jobs); `1` — every board failed;
  `2` — bad arguments, raised before any network request.

## Processing order (important for cost)

```
scrape listings → --title-filter/--location-filter → --dedupe → --fetch-description
```

Descriptions are fetched only for jobs that survived filtering and deduplication, so
combining `--title-filter`/`--dedupe` with `--fetch-description` is much cheaper than
fetching first. Indeed returns descriptions inline and is never fetched twice.

## Python API

```python
from jobspy_lite import scrape_jobs

results = scrape_jobs(
    site_name=["indeed", "linkedin", "arbeitsagentur", "stepstone"],
    search_term="Softwareentwickler",
    location="Berlin, Germany",
    country_indeed="germany",
    results_wanted=20,
    fetch_description=True,
    dedupe=True,
)
for job in results:                     # results is a list[JobPost]
    print(job.site, job.title, job.company, job.job_url)
print(results.errors)                   # {site: message} for boards that failed
print(results.warnings)                 # {site: [messages]}
print(results.filtered_out, results.duplicates_removed)
```

`job.model_dump()` gives a flat dict (location as a string, enums as values).
A single board can be driven directly:

```python
from jobspy_lite.stepstone import StepStone
from jobspy_lite.model import ScraperInput

scraper = StepStone()
jobs = scraper.scrape(ScraperInput(search_term="Python", location="Berlin"))
jobs = [scraper.enrich(job) for job in jobs]   # descriptions, if needed
```

## Common agent mistakes

| Mistake | Correct behaviour |
|---|---|
| `--site all` | there is no `all` value — omit `--site` to query all four boards |
| Expecting `-n 50` to mean 50 jobs total | it means up to 50 **per board** |
| Treating exit `0` as "found jobs" | `0` means the boards answered; check the JSONL line count or `results.errors` |
| Searching German Indeed without `--country-indeed germany` | default is `usa` and results will be empty or irrelevant |
| Expecting `--hours-old` to work on StepStone | it is ignored with a warning |
| `--fetch-description` with a large `-n` on all boards | hundreds of page requests, slow and likely `429`; filter and dedupe first, keep `-n` small |
| Expecting `--fields` to shape CSV columns | CSV always writes all columns; `--fields` affects JSONL/JSON/stdout |
| Retrying in a loop after `429`/`403` | the board rate-limited the IP; wait, lower `-n`, or pass `--proxies` |
| Cyrillic output mangled on Windows | set `PYTHONIOENCODING=utf-8` |
| Parsing stderr as data | stderr carries logs and counters; only stdout is JSONL |
| Assuming `--remote` works on LinkedIn | LinkedIn ignores it with a warning |
| Trusting empty salary fields on Arbeitsagentur | the API publishes only the salary type, never amounts |

## Limitations

- LinkedIn guest search returns at most 1000 results and blocks busy IPs with `403`/`429`;
  there are no automatic retries (same as upstream JobSpy).
- StepStone depends on `curl_cffi` TLS impersonation and page markup; `--stepstone-impersonate`
  can switch the fingerprint if the default stops working.
- Arbeitsagentur exposes no salary amounts; its public key has rate limits.
- Indeed needs an explicit country outside the US.
- Only public listings are read: no sign-in, no applications, no captcha bypass.

## Disclaimer

Not affiliated with LinkedIn, Indeed, StepStone or the Bundesagentur für Arbeit. Scraping may
violate a board's terms of service; the user is responsible for compliance, for rate limits
and for any personal data processed. Software is provided "as is" under the MIT licence,
without warranty. Full text: `DISCLAIMER.md` in the repository.
