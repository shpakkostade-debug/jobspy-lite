import pytest

from jobspy_lite.filters import compile_title, filter_jobs
from jobspy_lite.model import Country, Location


def test_title_filter_is_case_insensitive_regex(make_job):
    jobs = [
        make_job(title="Data Analyst"),
        make_job(title="Data Engineer"),
    ]
    assert [job.title for job in filter_jobs(jobs, title="analyst")] == [
        "Data Analyst"
    ]
    assert [job.title for job in filter_jobs(jobs, title="^data (analyst|sci)")] == [
        "Data Analyst"
    ]


def test_location_filter_matches_displayed_location(make_job):
    dortmund = Location(city="Dortmund", country=Country.GERMANY)
    berlin = Location(city="Berlin", country=Country.GERMANY)
    jobs = [
        make_job(job_url="https://a", location=dortmund),
        make_job(job_url="https://b", location=berlin),
    ]
    kept = filter_jobs(jobs, location="DORTMUND")
    assert [job.job_url for job in kept] == ["https://a"]


def test_both_filters_must_match(make_job):
    job = make_job(
        title="Data Analyst",
        location=Location(city="Dortmund", country=Country.GERMANY),
    )
    assert filter_jobs([job], title="analyst", location="dortmund") == [job]
    assert filter_jobs([job], title="analyst", location="berlin") == []


def test_no_filters_keeps_everything(make_job):
    jobs = [make_job(job_url="https://a"), make_job(job_url="https://b")]
    assert filter_jobs(jobs) == jobs


def test_job_without_location_is_kept_only_without_location_filter(make_job):
    job = make_job(location=None)
    assert filter_jobs([job]) == [job]
    assert filter_jobs([job], location="dortmund") == []


def test_bad_regex_raises(make_job):
    with pytest.raises(ValueError, match="Invalid title filter"):
        filter_jobs([make_job()], title="([")


def test_compile_title():
    assert compile_title(None) is None
    assert compile_title("") is None
    assert compile_title("analyst").search("DATA ANALYST")
