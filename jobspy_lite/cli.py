from __future__ import annotations

import argparse
import csv
import inspect
import json
import os
import sys
from collections.abc import Sequence
from importlib.metadata import PackageNotFoundError, version

from jobspy_lite import scrape_jobs
from jobspy_lite.model import DescriptionFormat, JobPost, JobType

FIELDS = list(JobPost.model_fields)
PREVIEW = (
    "site title company location date_posted job_type is_remote "
    "min_amount max_amount currency interval job_url"
).split()
FORMATS = (".csv", ".json", ".jsonl")

DESCRIPTION = """\
Search Indeed, LinkedIn, Arbeitsagentur and StepStone, print one JSON
object per job (JSON Lines).
Fields a board did not give are left out. Errors and warnings go to stderr.

examples:
  jobspy-lite "software engineer" --location Berlin -n 20
  jobspy-lite "data analyst" --country-indeed Germany -o jobs.jsonl
  jobspy-lite nurse --site indeed --hours-old 24 --remote
  jobspy-lite "pflegekraft" --site arbeitsagentur,stepstone -n 30

exit codes:
  0    at least one board answered, also with no jobs
  1    every board failed
  2    usage error
"""


def package_version() -> str:
    try:
        return version("jobspy-lite")
    except PackageNotFoundError:
        return "0.0.0"


def commas(text: str) -> list[str]:
    return [name for part in text.split(",") if (name := part.strip())]


def fields(text: str) -> list[str]:
    names = FIELDS if text == "all" else commas(text)
    if unknown := [name for name in names if name not in FIELDS]:
        raise argparse.ArgumentTypeError(
            f"unknown {', '.join(unknown)}; use all or any of "
            f"{', '.join(FIELDS)}"
        )
    return list(dict.fromkeys(names))


def output_path(text: str) -> str:
    if not text.lower().endswith(FORMATS):
        raise argparse.ArgumentTypeError(
            f"{text}: use .csv, .json or .jsonl"
        )
    return text


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="jobspy-lite",
        usage="%(prog)s [QUERY] [options]",
        description=DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        argument_default=argparse.SUPPRESS,
        allow_abbrev=False,
    )
    p.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {package_version()}",
    )
    add = p.add_argument_group("search").add_argument
    add("search_term", nargs="?", metavar="QUERY", help="search term")
    add("--location", metavar="TEXT", help="city, state or country")
    add("--distance", type=int, metavar="N", help="miles (default 50)")
    add(
        "--remote",
        dest="is_remote",
        action="store_true",
        help="remote jobs only",
    )
    add(
        "--job-type",
        metavar="T",
        choices=[t.value for t in JobType],
        help="one of the job types",
    )
    add("--hours-old", type=int, metavar="N", help="posted in last N hours")
    add(
        "--easy-apply",
        action="store_true",
        help="jobs hosted on the board",
    )
    add(
        "--country-indeed",
        metavar="C",
        help="Indeed country (default usa)",
    )
    add(
        "-n",
        "--results-wanted",
        type=int,
        metavar="N",
        default=5,
        help="per board (default 5)",
    )
    add("--offset", type=int, metavar="N", help="skip first N results")
    add = p.add_argument_group("boards").add_argument
    add(
        "--site",
        dest="site_name",
        type=commas,
        default=["indeed", "linkedin", "arbeitsagentur", "stepstone"],
        metavar="LIST",
        help=(
            "comma list of indeed,linkedin,arbeitsagentur,stepstone "
            "(default all four)"
        ),
    )
    add(
        "--fetch-description",
        action="store_true",
        help=(
            "fetch each job's page, only for the jobs left after "
            "filtering and --dedupe"
        ),
    )
    add(
        "--description-format",
        choices=[f.value for f in DescriptionFormat],
        help="markdown (default), html, plain",
    )
    add(
        "--enforce-annual-salary",
        action="store_true",
        help="convert pay to yearly",
    )
    add(
        "--linkedin-company-ids",
        type=lambda text: [int(n) for n in commas(text)],
        metavar="IDS",
        help="LinkedIn company ids",
    )
    add(
        "--arbeitsagentur-api-key",
        metavar="KEY",
        help="X-API-Key for Arbeitsagentur (default: the public jobsuche key)",
    )
    add(
        "--stepstone-impersonate",
        metavar="NAME",
        help="curl_cffi browser for StepStone (default chrome)",
    )
    add("--proxies", type=commas, metavar="LIST", help="comma list of URLs")
    add("--ca-cert", metavar="PATH", help="CA bundle for the proxy")
    add("--user-agent", metavar="TEXT", help="User-Agent header")
    add = p.add_argument_group("output").add_argument
    add(
        "--fields",
        type=fields,
        metavar="LIST",
        help="comma list of fields, or all",
    )
    add(
        "--title-filter",
        metavar="REGEX",
        help="keep jobs whose title matches REGEX (case-insensitive)",
    )
    add(
        "--location-filter",
        metavar="TEXT",
        help="keep jobs whose location contains TEXT (case-insensitive)",
    )
    add(
        "--dedupe",
        action="store_true",
        help="merge the same job found on several boards",
    )
    add(
        "-o",
        "--output",
        type=output_path,
        metavar="PATH",
        help="write .jsonl, .json or .csv instead of stdout",
    )
    add("--verbose", type=int, choices=[0, 1, 2], help="0 errors, 2 all")
    return p


def rows(jobs: Sequence[JobPost], names: Sequence[str]) -> list[dict]:
    flattened = [job.model_dump() for job in jobs]
    return [
        {
            name: row[name]
            for name in names
            if row.get(name) is not None
        }
        for row in flattened
    ]


def dumps(value: object) -> str:
    return json.dumps(
        value, default=str, ensure_ascii=False, separators=(",", ":")
    )


def save(jobs: Sequence[JobPost], path: str, names: Sequence[str]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as saved:
        if path.lower().endswith(".csv"):
            writer = csv.DictWriter(saved, fieldnames=list(FIELDS))
            writer.writeheader()
            for job in jobs:
                row = job.model_dump()
                writer.writerow(
                    {
                        name: ""
                        if row.get(name) is None
                        else row[name]
                        for name in FIELDS
                    }
                )
        elif path.lower().endswith(".json"):
            saved.write(dumps(rows(jobs, FIELDS)))
        else:
            for row in rows(jobs, names):
                saved.write(dumps(row) + "\n")


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    names = (
        args.fields
        if "fields" in args
        else (FIELDS if "output" in args else PREVIEW)
    )
    kwargs = {
        name: value
        for name, value in vars(args).items()
        if name in inspect.signature(scrape_jobs).parameters
    }
    try:
        results = scrape_jobs(**kwargs)
    except ValueError as e:
        print(f"jobspy-lite: {e}", file=sys.stderr)
        return 2

    if "output" in args:
        save(results, args.output, names)
        print(
            f"{len(results)} jobs written to {args.output}",
            file=sys.stderr,
        )
    else:
        for row in rows(results, names):
            print(dumps(row))

    if results.filtered_out:
        print(f"{results.filtered_out} jobs filtered out", file=sys.stderr)
    if results.duplicates_removed:
        print(
            f"{results.duplicates_removed} duplicates merged",
            file=sys.stderr,
        )
    if results.sites and len(results.errors) == len(results.sites):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
