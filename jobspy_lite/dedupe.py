from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable
from urllib.parse import urlsplit

from jobspy_lite.model import JobPost

__all__ = ["dedupe_jobs"]

GENDER = re.compile(
    r"\((?:[mwdfxa]|gn)(?:\s*/\s*[mwdfxa])*\)|\(all genders\)",
    re.IGNORECASE,
)
PUNCTUATION = re.compile(r"[^\w\s]")
COMPANY_SUFFIXES = frozenset(
    {
        "ag",
        "co",
        "ev",
        "gbr",
        "gmbh",
        "inc",
        "kg",
        "kgaa",
        "llc",
        "ltd",
        "mbh",
        "ohg",
        "plc",
        "se",
        "ug",
        "und",
        "and",
    }
)
TITLE_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "bei",
        "das",
        "der",
        "die",
        "for",
        "für",
        "fur",
        "im",
        "in",
        "of",
        "the",
        "und",
    }
)
SIMILARITY = 0.85


def _words(text: str | None) -> list[str]:
    """Lowercase words, without the (m/w/d) markers and punctuation."""
    return PUNCTUATION.sub(" ", GENDER.sub(" ", text or "").lower()).split()


def _company_key(company: str | None) -> str:
    return " ".join(
        word for word in _words(company) if word not in COMPANY_SUFFIXES
    )


def _title_key(title: str | None) -> str:
    return " ".join(
        word for word in _words(title) if word not in TITLE_STOPWORDS
    )


def _direct_key(url: str | None) -> str | None:
    """The employer's page without the query string and trailing slash."""
    if not url:
        return None
    parts = urlsplit(url)
    host = parts.netloc.lower().removeprefix("www.")
    if not host:
        return None
    return f"{host}{parts.path.rstrip('/').lower()}"


def _similar(first: str, second: str) -> bool:
    left, right = set(first.split()), set(second.split())
    if not left or not right:
        return False
    return len(left & right) / len(left | right) >= SIMILARITY


def _score(job: JobPost) -> tuple[bool, int]:
    """Pay first, then the number of filled fields.

    Descriptions are fetched after the merge, so they say nothing about how
    complete a record is at this point.
    """
    filled = sum(
        1
        for name in JobPost.model_fields
        if name != "description"
        and getattr(job, name) not in (None, [], "")
    )
    return bool(job.min_amount or job.max_amount), filled


def _merge(group: list[JobPost]) -> JobPost:
    if len(group) == 1:
        return group[0]
    best = max(group, key=_score)
    updates = {
        name: getattr(job, name)
        for job in group
        for name in JobPost.model_fields
        if getattr(best, name) is None and getattr(job, name) is not None
    }
    emails = sorted({email for job in group for email in job.emails or []})
    if emails:
        updates["emails"] = emails
    job_types = list(
        dict.fromkeys(
            job_type for job in group for job_type in job.job_type or []
        )
    )
    if job_types:
        updates["job_type"] = job_types
    return best.model_copy(update=updates) if updates else best


def dedupe_jobs(jobs: Iterable[JobPost]) -> list[JobPost]:
    """
    One record per vacancy.

    Jobs are merged when they share a normalised title and company, the same
    employer page (``job_url_direct``), or nearly the same title at the same
    company. The most complete record is kept; its empty fields are filled
    from the others, and the order of first appearance is preserved.
    """
    jobs = list(jobs)
    parent = list(range(len(jobs)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(first: int, second: int) -> None:
        parent[find(second)] = find(first)

    exact: dict[tuple[str, str], int] = {}
    direct: dict[str, int] = {}
    for index, job in enumerate(jobs):
        title, company = _title_key(job.title), _company_key(job.company)
        if title and company:
            union(index, exact.setdefault((title, company), index))
        url = _direct_key(job.job_url_direct)
        if url:
            union(index, direct.setdefault(url, index))

    by_company: dict[str, list[int]] = defaultdict(list)
    for index, job in enumerate(jobs):
        company = _company_key(job.company)
        if company:
            by_company[company].append(index)
    for indices in by_company.values():
        for position, first in enumerate(indices):
            for second in indices[position + 1 :]:
                if _similar(
                    _title_key(jobs[first].title),
                    _title_key(jobs[second].title),
                ):
                    union(first, second)

    clusters: dict[int, list[JobPost]] = defaultdict(list)
    for index, job in enumerate(jobs):
        clusters[find(index)].append(job)
    return [_merge(group) for group in clusters.values()]
