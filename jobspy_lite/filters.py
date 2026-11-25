from __future__ import annotations

import re
from collections.abc import Iterable

from jobspy_lite.model import JobPost

__all__ = ["filter_jobs"]


def compile_title(title: str | None) -> re.Pattern[str] | None:
    """The title filter as a pattern, so a bad regex fails before scraping."""
    if not title:
        return None
    try:
        return re.compile(title, re.IGNORECASE)
    except re.error as e:
        raise ValueError(f"Invalid title filter {title!r}: {e}") from None


def filter_jobs(
    jobs: Iterable[JobPost],
    title: str | None = None,
    location: str | None = None,
) -> list[JobPost]:
    """
    The jobs that match both filters.

    ``title`` is a case-insensitive regular expression, ``location`` a
    case-insensitive substring of the displayed location. A missing filter
    keeps every job.
    :raises ValueError: the title filter isn't a valid regex
    """
    pattern = compile_title(title)
    place = location.strip().lower() if location else None
    return [
        job
        for job in jobs
        if (pattern is None or pattern.search(job.title))
        and (
            place is None
            or place
            in (
                job.location.display_location().lower()
                if job.location
                else ""
            )
        )
    ]
