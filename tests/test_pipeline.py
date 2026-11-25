import pytest

import jobspy_lite
from jobspy_lite import scrape_jobs
from jobspy_lite.model import Scraper, Site


def fake_board(monkeypatch, jobs, scraped, enriched):
    class Fake(Scraper):
        def scrape(self, scraper_input):
            scraped.append(scraper_input)
            return [job.model_copy() for job in jobs]

        def enrich(self, job):
            enriched.append(job.title)
            return job.model_copy(update={"description": "job page"})

    monkeypatch.setattr(
        jobspy_lite, "SCRAPER_MAPPING", {Site.INDEED: Fake}
    )


def test_descriptions_are_fetched_only_for_survivors(monkeypatch, make_job):
    jobs = [
        make_job(job_url="https://a", job_level="Senior"),
        make_job(
            title="Data Analyst (m/w/d)",
            company="Acme GmbH",
            job_url="https://b",
            min_amount=60000,
            max_amount=70000,
        ),
        make_job(title="Sales Manager", job_url="https://c"),
    ]
    scraped, enriched = [], []
    fake_board(monkeypatch, jobs, scraped, enriched)

    results = scrape_jobs(
        site_name=["indeed"],
        search_term="analyst",
        title_filter="analyst",
        dedupe=True,
        fetch_description=True,
    )

    assert len(results) == 1
    assert results[0].description == "job page"
    assert results[0].site == "indeed"
    assert enriched == ["Data Analyst (m/w/d)"]  # one page, not three
    assert results.filtered_out == 1
    assert results.duplicates_removed == 1


def test_without_fetch_description_no_pages_are_opened(monkeypatch, make_job):
    scraped, enriched = [], []
    fake_board(monkeypatch, [make_job()], scraped, enriched)

    results = scrape_jobs(site_name=["indeed"], search_term="analyst")

    assert len(results) == 1
    assert results[0].description is None
    assert enriched == []


def test_bad_regex_fails_before_scraping(monkeypatch, make_job):
    scraped, enriched = [], []
    fake_board(monkeypatch, [make_job()], scraped, enriched)

    with pytest.raises(ValueError, match="Invalid title filter"):
        scrape_jobs(site_name=["indeed"], title_filter="([")

    assert scraped == []
