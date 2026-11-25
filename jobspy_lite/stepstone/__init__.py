from __future__ import annotations

import json
import random
import time
from datetime import date, timedelta
from itertools import cycle
from urllib.parse import quote

from bs4 import BeautifulSoup
from bs4.element import Tag
from curl_cffi import requests as curl_requests

from jobspy_lite.model import (
    Compensation,
    Country,
    JobPost,
    Location,
    Scraper,
    ScraperInput,
)
from jobspy_lite.stepstone.constant import (
    base_url,
    default_impersonate,
    headers,
    job_id,
    job_id_from_url,
    job_type_keywords,
    jobs_per_page,
    max_pages,
    pay_units,
    remote_keywords,
    timeago,
    umlauts,
)
from jobspy_lite.util import (
    RotatingProxySession,
    check_status,
    description_fields,
    fill_missing,
    get_enum_from_job_type,
)


class StepStone(Scraper):
    """The StepStone job board, scraped through curl_cffi's browser TLS."""

    delay = (1, 2)

    def scrape(self, scraper_input: ScraperInput) -> list[JobPost]:
        self.scraper_input = scraper_input
        self.session = curl_requests.Session(
            impersonate=scraper_input.stepstone_impersonate
            or default_impersonate
        )
        self.session.headers.update(headers)
        if scraper_input.user_agent:
            self.session.headers["user-agent"] = scraper_input.user_agent
        self.proxy_cycle = (
            cycle(
                map(RotatingProxySession.format_proxy, scraper_input.proxies)
            )
            if scraper_input.proxies
            else None
        )
        if scraper_input.hours_old:
            self.warn("hours_old isn't supported, ignoring it")

        url = self._search_url()
        jobs: list[JobPost] = []
        seen: set[str] = set()
        skip = scraper_input.offset
        page = 1

        while len(jobs) < scraper_input.results_wanted and page <= max_pages:
            if page > 1:
                time.sleep(random.uniform(*self.delay))
            self.log.info(f"search page: {page}")
            try:
                response = self._get(url, page=page)
                check_status(response)
            except Exception as e:
                self.fail(str(e))
                break

            soup = BeautifulSoup(response.text, "html.parser")
            cards = soup.select('[data-at="job-item"]')
            if not cards:
                self.warn(
                    f"no job cards on page {page} "
                    "(no results, or blocked)"
                )
                break

            new = []
            for card in cards:
                identifier = self._card_id(card)
                if identifier and identifier not in seen:
                    seen.add(identifier)
                    new.append((identifier, card))

            for identifier, card in new:
                if skip:
                    skip -= 1
                    continue
                try:
                    jobs.append(self._process_card(card, identifier))
                except Exception as e:
                    self.log.warning(f"skipping job: {e}")
                    continue
                if len(jobs) >= scraper_input.results_wanted:
                    break

            if len(cards) < jobs_per_page or not new:
                break
            page += 1

        return jobs

    def _get(self, url: str, **params: object) -> curl_requests.Response:
        """One retry: StepStone sometimes resets the HTTP/2 stream"""
        for attempt in (1, 2):
            kwargs: dict[str, object] = {"params": params, "timeout": 30}
            if self.proxy_cycle:
                kwargs["proxies"] = next(self.proxy_cycle)
            if self.scraper_input.ca_cert:
                kwargs["verify"] = str(self.scraper_input.ca_cert)
            try:
                return self.session.get(url, **kwargs)
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(1)
        raise AssertionError("unreachable")

    def _search_url(self) -> str:
        def slug(text: str) -> str:
            return quote(
                "-".join(
                    text.lower()
                    .translate(umlauts)
                    .replace("/", " ")
                    .split()
                )
            )

        search_term = (self.scraper_input.search_term or "").strip()
        location = (self.scraper_input.location or "").strip()
        if search_term and location:
            return f"{base_url}/jobs/{slug(search_term)}/in-{slug(location)}"
        if search_term:
            return f"{base_url}/jobs/{slug(search_term)}"
        if location:
            return f"{base_url}/jobs/in-{slug(location)}"
        return f"{base_url}/jobs"

    @staticmethod
    def _card_id(card: Tag) -> str | None:
        match = job_id.search(str(card.get("id", "")))
        if match:
            return match.group(1)
        link = card.select_one('[data-at="job-item-title"]')
        if link and link.get("href"):
            match = job_id_from_url.search(str(link["href"]))
            if match:
                return match.group(1)
        return None

    def _process_card(self, card: Tag, identifier: str) -> JobPost:
        link = card.select_one('[data-at="job-item-title"]')
        if link is None:
            raise ValueError("no title")
        title = " ".join(link.get_text(" ", strip=True).split())
        job_url = str(link.get("href") or "").split("?")[0]
        if job_url.startswith("/"):
            job_url = base_url + job_url
        company_tag = card.select_one('[data-at="job-item-company-name"]')
        location_tag = card.select_one('[data-at="job-item-location"]')
        time_tag = card.select_one('[data-at="job-item-timeago"]')
        location = self._location(location_tag)
        title_lower = title.lower()
        location_text = (
            " ".join(location_tag.get_text(" ", strip=True).split())
            if location_tag
            else ""
        )
        job_types = [
            job_type
            for keyword, name in job_type_keywords.items()
            if keyword.lower() in title_lower
            and (job_type := get_enum_from_job_type(name))
        ]
        data: dict[str, object] = {
            "id": f"ss-{identifier}",
            "title": title,
            "company": (
                " ".join(company_tag.get_text(" ", strip=True).split())
                if company_tag
                else None
            ),
            "location": location,
            "date_posted": self._date(time_tag),
            "job_type": list(dict.fromkeys(job_types)) or None,
            "job_url": job_url,
            "is_remote": (
                True
                if any(
                    word in f"{title_lower} {location_text.lower()}"
                    for word in remote_keywords
                )
                else None
            ),
        }
        return JobPost(**data)

    @staticmethod
    def _location(tag: Tag | None) -> Location | None:
        if tag is None:
            return None
        parts = [
            part.strip()
            for part in tag.get_text(" ", strip=True).split(",")
            if part.strip()
        ]
        if not parts:
            return None
        return Location(
            city=parts[0],
            state=", ".join(parts[1:]) or None,
            country=Country.GERMANY,
        )

    @staticmethod
    def _date(tag: Tag | None) -> date | None:
        if tag is None:
            return None
        text = tag.get_text(" ", strip=True).lower()
        if "heute" in text:
            return date.today()
        if "gestern" in text:
            return date.today() - timedelta(days=1)
        match = timeago.search(text)
        if not match:
            return None
        unit = match[2].lower()
        if unit.startswith("stund"):
            days = 0
        elif unit.startswith("tag"):
            days = int(match[1])
        elif unit.startswith("woche"):
            days = int(match[1]) * 7
        else:
            days = int(match[1]) * 30
        return date.today() - timedelta(days=days)

    def enrich(self, job: JobPost) -> JobPost:
        """The description and page details, fetched after filtering."""
        if job.description is not None:
            return job
        details = self._fetch_details(job.job_url)
        return (
            job.model_copy(update=fill_missing(job, details))
            if details
            else job
        )

    def _fetch_details(self, job_url: str) -> dict[str, object]:
        """The description, pay and company data from the job page's JSON-LD"""
        try:
            response = self._get(job_url)
            check_status(response)
        except Exception as e:
            self.warn(f"{job_url}: {e}")
            return {}
        soup = BeautifulSoup(response.text, "html.parser")
        posting = None
        for block in soup.select('script[type="application/ld+json"]'):
            try:
                data = json.loads(block.string or "")
            except ValueError:
                continue
            for entry in data if isinstance(data, list) else [data]:
                if isinstance(entry, dict) and entry.get("@type") == "JobPosting":
                    posting = entry
                    break
            if posting:
                break
        if not posting:
            self.warn(f"{job_url}: no JobPosting data")
            return {}

        html = posting.get("description")
        fields: dict[str, object] = (
            description_fields(html, self.scraper_input.description_format)
            if html
            else {}
        )
        fields.update(self._salary(posting.get("baseSalary")))
        organization = posting.get("hiringOrganization") or {}
        logo = organization.get("logo")
        if isinstance(logo, dict):
            logo = logo.get("url")
        same_as = organization.get("sameAs")
        if isinstance(same_as, list):
            same_as = same_as[0] if same_as else None
        address = (
            (posting.get("jobLocation") or {}).get("address") or {}
        )
        employment = posting.get("employmentType")
        employment = (
            employment[0] if isinstance(employment, list) and employment else employment
        )
        job_type = (
            get_enum_from_job_type(str(employment).lower().replace("_", ""))
            if employment
            else None
        )
        posted = posting.get("datePosted")
        industry = posting.get("industry")
        return {
            **fields,
            "company": organization.get("name"),
            "company_url": same_as,
            "company_logo": logo,
            "company_industry": (
                ", ".join(industry) if isinstance(industry, list) else industry
            ),
            "date_posted": (
                date.fromisoformat(str(posted)[:10]) if posted else None
            ),
            "job_type": [job_type] if job_type else None,
            "location": Location(
                city=address.get("addressLocality") or None,
                state=address.get("addressRegion") or None,
                country=Country.GERMANY,
            ),
        }

    @staticmethod
    def _salary(base: object) -> dict[str, object]:
        if not isinstance(base, dict):
            return {}
        value = base.get("value") or {}
        if not isinstance(value, dict):
            return {}
        interval = pay_units.get(str(value.get("unitText") or "").upper())
        low, high = value.get("minValue"), value.get("maxValue")
        amount = value.get("value")
        if low is None and amount is not None:
            low = high = amount
        if interval is None or (low is None and high is None):
            return {}
        currency = base.get("currency") or "EUR"
        return Compensation(
            interval=interval,
            min_amount=low,
            max_amount=high,
            currency=currency,
        ).model_dump()
