import pytest

from jobspy_lite.model import JobPost


@pytest.fixture
def make_job():
    def make(
        title: str = "Data Analyst",
        company: str | None = "Acme",
        job_url: str = "https://example.com/job",
        **fields: object,
    ) -> JobPost:
        return JobPost(
            title=title, company=company, job_url=job_url, **fields
        )

    return make
