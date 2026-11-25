from jobspy_lite.arbeitsagentur import Arbeitsagentur
from jobspy_lite.arbeitsagentur.model import JobDetails
from jobspy_lite.linkedin import LinkedIn
from jobspy_lite.model import DescriptionFormat, ScraperInput
from jobspy_lite.stepstone import StepStone


def test_arbeitsagentur_enrich_fills_description_and_remote(
    monkeypatch, make_job
):
    scraper = Arbeitsagentur()
    scraper.scraper_input = ScraperInput(
        description_format=DescriptionFormat.MARKDOWN
    )
    asked = []
    details = JobDetails(
        stellenangebotsTitel="Data Analyst",
        referenznummer="123",
        homeofficemoeglich=True,
        stellenangebotsBeschreibung="<p>Hello <b>there</b></p>",
    )
    monkeypatch.setattr(
        scraper, "_fetch_details", lambda refnr: asked.append(refnr) or details
    )

    job = make_job(id="aa-123", is_remote=None)
    enriched = scraper.enrich(job)

    assert asked == ["123"]  # the aa- prefix is stripped
    assert enriched.is_remote is True
    assert "Hello" in enriched.description


def test_arbeitsagentur_enrich_skips_a_complete_job(monkeypatch, make_job):
    scraper = Arbeitsagentur()
    scraper.scraper_input = ScraperInput()

    def unexpected(refnr):
        raise AssertionError("no request expected")

    monkeypatch.setattr(scraper, "_fetch_details", unexpected)
    job = make_job(id="aa-123", is_remote=True, description="text")

    assert scraper.enrich(job) is job


def test_stepstone_enrich_keeps_its_own_data(monkeypatch, make_job):
    scraper = StepStone()
    asked = []
    monkeypatch.setattr(
        scraper,
        "_fetch_details",
        lambda url: asked.append(url)
        or {"description": "page text", "min_amount": 50000},
    )

    job = make_job(job_url="https://stepstone/1", min_amount=60000)
    enriched = scraper.enrich(job)

    assert enriched.min_amount == 60000  # its own data wins
    assert enriched.description == "page text"
    assert asked == ["https://stepstone/1"]

    described = make_job(description="already there")
    assert scraper.enrich(described) is described
    assert asked == ["https://stepstone/1"]


def test_linkedin_enrich_strips_the_prefix(monkeypatch, make_job):
    scraper = LinkedIn()
    asked = []
    monkeypatch.setattr(
        scraper,
        "_fetch_details",
        lambda job_id: asked.append(job_id)
        or {"description": "text", "job_level": "Senior"},
    )

    enriched = scraper.enrich(make_job(id="li-42"))

    assert asked == ["42"]
    assert enriched.job_level == "Senior"
    assert enriched.description == "text"

    without_id = make_job()
    assert scraper.enrich(without_id) is without_id
    assert asked == ["42"]
