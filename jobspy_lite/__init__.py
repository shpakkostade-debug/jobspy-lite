from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from pydantic import ValidationError

from jobspy_lite.arbeitsagentur import Arbeitsagentur
from jobspy_lite.dedupe import dedupe_jobs
from jobspy_lite.filters import compile_title, filter_jobs
from jobspy_lite.indeed import Indeed
from jobspy_lite.linkedin import LinkedIn
from jobspy_lite.stepstone import StepStone
from jobspy_lite.model import (
    Country,
    DescriptionFormat,
    JobPost,
    JobType,
    Scraper,
    ScraperInput,
    Site,
)
from jobspy_lite.util import configure_logging

__all__ = ["scrape_jobs", "ScrapeResults", "dedupe_jobs", "filter_jobs"]

SCRAPER_MAPPING: dict[Site, type[Scraper]] = {
    Site.INDEED: Indeed,
    Site.LINKEDIN: LinkedIn,
    Site.ARBEITSAGENTUR: Arbeitsagentur,
    Site.STEPSTONE: StepStone,
}


class ScrapeResults(list[JobPost]):
    """The jobs, plus per-site errors and warnings."""

    def __init__(
        self,
        jobs: Iterable[JobPost] = (),
        *,
        sites: Iterable[str] = (),
        errors: dict[str, str] | None = None,
        warnings: dict[str, list[str]] | None = None,
        duplicates_removed: int = 0,
        filtered_out: int = 0,
    ) -> None:
        super().__init__(jobs)
        self.sites = list(sites)
        self.errors = errors or {}
        self.warnings = warnings or {}
        self.duplicates_removed = duplicates_removed
        self.filtered_out = filtered_out


def scrape_jobs(
    site_name: str | Site | Iterable[str | Site] = (
        "indeed",
        "linkedin",
        "arbeitsagentur",
        "stepstone",
    ),
    search_term: str | None = None,
    location: str | None = None,
    distance: int | None = 50,
    is_remote: bool | None = False,
    job_type: str | JobType | None = None,
    easy_apply: bool | None = None,
    results_wanted: int | None = 15,
    country_indeed: str | Country | None = "usa",
    proxies: str | Iterable[str] | None = None,
    ca_cert: str | Path | None = None,
    description_format: str | DescriptionFormat | None = "markdown",
    linkedin_company_ids: Iterable[int] | None = None,
    arbeitsagentur_api_key: str | None = None,
    stepstone_impersonate: str | None = None,
    offset: int | None = 0,
    hours_old: int | None = None,
    enforce_annual_salary: bool | None = False,
    verbose: int | None = 1,
    user_agent: str | None = None,
    fetch_description: bool | None = False,
    dedupe: bool | None = False,
    title_filter: str | None = None,
    location_filter: str | None = None,
) -> ScrapeResults:
    """
    Scrapes the chosen boards concurrently.

    The jobs are filtered, then deduplicated, and only the survivors have
    their pages fetched when ``fetch_description`` is on.

    :param title_filter: keep jobs whose title matches this regex
    :param location_filter: keep jobs whose location contains this text
    :return: the jobs, with per-site errors and warnings attached
    :raises ValueError: an argument is invalid
    """
    arguments = dict(locals())
    for name in ("dedupe", "title_filter", "location_filter"):
        arguments.pop(name, None)
    try:
        scraper_input = ScraperInput.model_validate(
            {
                name: value
                for name, value in arguments.items()
                if value is not None
                and not (isinstance(value, str) and not value)
            }
        )
    except ValidationError as e:
        messages = []
        for error in e.errors():
            name, value = error["loc"][0], error["input"]
            shown = (
                type(value).__name__
                if name == "proxies"
                else repr(value)
            )
            messages.append(f"Invalid {name}: {shown}. {error['msg']}")
        raise ValueError("; ".join(messages)) from None
    configure_logging(scraper_input.verbose)
    compile_title(title_filter)
    wants_description = scraper_input.fetch_description
    if wants_description:
        scraper_input = scraper_input.model_copy(
            update={"fetch_description": False}
        )

    def scrape_site(site: Site) -> tuple[str, Scraper, list[JobPost]]:
        scraper = SCRAPER_MAPPING[site]()
        scraped_data = scraper.scrape(scraper_input)
        scraper.log.info("finished scraping")
        return site.value, scraper, scraped_data

    with ThreadPoolExecutor() as executor:
        results = list(
            executor.map(scrape_site, dict.fromkeys(scraper_input.site_name))
        )

    jobs = [
        (
            job.annualised()
            if scraper_input.enforce_annual_salary
            else job
        ).model_copy(update={"site": site})
        for site, _, site_jobs in results
        for job in site_jobs
    ]
    jobs.sort(
        key=lambda job: (
            job.site or "",
            -(job.date_posted.toordinal() if job.date_posted else 0),
        )
    )
    found = len(jobs)
    if title_filter or location_filter:
        jobs = filter_jobs(jobs, title_filter, location_filter)
    after_filter = len(jobs)
    if dedupe:
        jobs = dedupe_jobs(jobs)
    if wants_description:
        jobs = _enrich(jobs, results)
    return ScrapeResults(
        jobs,
        sites=[site for site, _, _ in results],
        errors={site: s.error for site, s, _ in results if s.error},
        warnings={
            site: s.warnings for site, s, _ in results if s.warnings
        },
        duplicates_removed=after_filter - len(jobs),
        filtered_out=found - after_filter,
    )


def _enrich(
    jobs: list[JobPost],
    results: list[tuple[str, Scraper, list[JobPost]]],
) -> list[JobPost]:
    """Fetches the job pages, one board at a time and boards in parallel."""
    scrapers = {site: scraper for site, scraper, _ in results}
    by_site: dict[str, list[JobPost]] = defaultdict(list)
    for job in jobs:
        by_site[job.site or ""].append(job)

    def describe(pair: tuple[str, list[JobPost]]) -> list[JobPost]:
        site, site_jobs = pair
        scraper = scrapers.get(site)
        return (
            [scraper.enrich(job) for job in site_jobs]
            if scraper
            else site_jobs
        )

    # The jobs are sorted by site, so grouping by site keeps the order.
    with ThreadPoolExecutor() as executor:
        return [
            job
            for site_jobs in executor.map(describe, by_site.items())
            for job in site_jobs
        ]
