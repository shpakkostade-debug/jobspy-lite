from jobspy_lite.dedupe import dedupe_jobs


def test_same_title_and_company_across_boards_merge(make_job):
    first = make_job(
        job_url="https://indeed/1", site="indeed", job_level="Senior"
    )
    second = make_job(
        title="Data Analyst (m/w/d)",
        company="Acme GmbH",
        job_url="https://stepstone/2",
        site="stepstone",
        min_amount=60000,
        max_amount=70000,
    )
    merged = dedupe_jobs([first, second])
    assert len(merged) == 1
    job = merged[0]
    assert job.site == "stepstone"  # the record with pay wins
    assert (job.min_amount, job.max_amount) == (60000, 70000)
    assert job.job_level == "Senior"  # filled from the other record


def test_pay_wins_over_description(make_job):
    described = make_job(
        job_url="https://indeed/1", description="a long text"
    )
    paid = make_job(job_url="https://stepstone/2", min_amount=60000)
    job = dedupe_jobs([described, paid])[0]
    assert job.min_amount == 60000
    assert job.description == "a long text"


def test_different_companies_do_not_merge(make_job):
    jobs = [
        make_job(company="Acme", job_url="https://a"),
        make_job(company="Globex", job_url="https://b"),
    ]
    assert len(dedupe_jobs(jobs)) == 2


def test_different_titles_at_one_company_do_not_merge(make_job):
    jobs = [
        make_job(title="Data Analyst", job_url="https://a"),
        make_job(title="Data Engineer", job_url="https://b"),
    ]
    assert len(dedupe_jobs(jobs)) == 2


def test_same_employer_page_merges(make_job):
    jobs = [
        make_job(
            title="Data Analyst",
            company="Acme",
            job_url="https://a",
            job_url_direct="https://jobs.acme.com/1?utm_source=indeed",
        ),
        make_job(
            title="Analyst, Data",
            company="Acme",
            job_url="https://b",
            job_url_direct="https://www.jobs.acme.com/1/",
        ),
    ]
    assert len(dedupe_jobs(jobs)) == 1


def test_order_and_single_records_are_kept(make_job):
    jobs = [
        make_job(title="Data Analyst", job_url="https://a"),
        make_job(title="Data Engineer", job_url="https://b"),
        make_job(title="Data Scientist", job_url="https://c"),
    ]
    assert dedupe_jobs(jobs) == jobs
