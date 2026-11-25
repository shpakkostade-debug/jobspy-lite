from __future__ import annotations

import base64
import math

from jobspy_lite.arbeitsagentur.constant import (
    api_url,
    default_api_key,
    headers,
    job_detail_url,
    jobs_per_page,
)
from jobspy_lite.arbeitsagentur.model import (
    JobDetails,
    JobSummary,
    SearchResponse,
)
from jobspy_lite.model import (
    Country,
    JobPost,
    JobType,
    Location,
    Scraper,
    ScraperInput,
)
from jobspy_lite.util import (
    RequestsRotating,
    check_status,
    create_session,
    description_fields,
    fill_missing,
)


class Arbeitsagentur(Scraper):
    """The Bundesagentur für Arbeit job board, through its public JSON API."""

    def scrape(self, scraper_input: ScraperInput) -> list[JobPost]:
        self.scraper_input = scraper_input
        self.session = create_session(
            RequestsRotating(scraper_input.proxies),
            scraper_input,
            headers | {"X-API-Key": scraper_input.arbeitsagentur_api_key or default_api_key},
        )
        jobs: list[JobPost] = []
        seen: set[str] = set()
        page = 1

        while len(jobs) < scraper_input.results_wanted:
            self.log.info(f"search page: {page}")
            try:
                response = self.session.get(
                    f"{api_url}/pc/v6/jobs", params=self._search_params(page)
                )
                check_status(response)
                search = SearchResponse.model_validate(response.json())
            except Exception as e:
                self.fail(str(e))
                break

            new = [
                job for job in search.ergebnisliste if job.referenznummer not in seen
            ]
            seen.update(job.referenznummer for job in new)
            for job in new:
                try:
                    jobs.append(self._process_job(job))
                except Exception as e:
                    self.log.warning(f"skipping job: {e}")
                    continue
                if len(jobs) >= scraper_input.results_wanted:
                    break

            if len(search.ergebnisliste) < jobs_per_page:
                break
            page += 1

        return jobs

    def _search_params(self, page: int) -> dict[str, str | int]:
        scraper_input = self.scraper_input
        params: dict[str, str | int | None] = {
            "was": scraper_input.search_term,
            "wo": scraper_input.location,
            "umkreis": scraper_input.distance,
            "size": jobs_per_page,
            "page": page,
        }
        if scraper_input.hours_old:
            params["veroeffentlichtseit"] = max(
                1, math.ceil(scraper_input.hours_old / 24)
            )
        return {
            name: value for name, value in params.items() if value is not None
        }

    def _process_job(self, job: JobSummary) -> JobPost:
        adresse = next(
            (
                location.adresse
                for location in job.stellenlokationen
                if location.adresse
            ),
            None,
        )
        full_time = job.arbeitszeitVollzeit
        part_time = any(
            (
                job.arbeitszeitTeilzeitVormittag,
                job.arbeitszeitTeilzeitNachmittag,
                job.arbeitszeitTeilzeitAbend,
                job.arbeitszeitTeilzeitFlexibel,
            )
        )
        job_types = [
            job_type
            for job_type, given in (
                (JobType.FULL_TIME, full_time),
                (JobType.PART_TIME, part_time),
            )
            if given
        ]
        return JobPost(
            id=f"aa-{job.referenznummer}",
            title=job.stellenangebotsTitel,
            company=job.firma,
            location=Location(
                city=adresse.ort if adresse else None,
                state=(
                    adresse.region.replace("_", " ").title()
                    if adresse and adresse.region
                    else None
                ),
                country=Country.GERMANY,
            ),
            date_posted=job.datumErsteVeroeffentlichung,
            job_type=job_types or None,
            job_url=job_detail_url.format(refnr=job.referenznummer),
            job_url_direct=job.externeURL,
            is_remote=job.homeofficemoeglich,
        )

    def enrich(self, job: JobPost) -> JobPost:
        """The description and home-office flag, fetched after filtering."""
        refnr = (job.id or "").removeprefix("aa-")
        if not refnr or (
            job.description is not None and job.is_remote is not None
        ):
            return job
        details = self._fetch_details(refnr)
        values: dict[str, object] = {
            "is_remote": details.homeofficemoeglich,
        }
        if details.stellenangebotsBeschreibung:
            values.update(
                description_fields(
                    details.stellenangebotsBeschreibung,
                    self.scraper_input.description_format,
                )
            )
        return job.model_copy(update=fill_missing(job, values))

    def _fetch_details(self, refnr: str) -> JobDetails:
        """The full record, including the description; empty on failure"""
        code = base64.b64encode(refnr.encode()).decode()
        try:
            response = self.session.get(f"{api_url}/pc/v4/jobdetails/{code}")
            check_status(response)
            return JobDetails.model_validate(response.json())
        except Exception as e:
            self.warn(f"job {refnr}: {e}")
            return JobDetails(stellenangebotsTitel="", referenznummer=refnr)
