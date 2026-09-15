"""
app/adapters/wuzzuf.py

Thin wrapper around the existing, previously-tested wuzzuf_collector.py.
Does not reimplement parsing -- reuses collect()/parse_feed() as-is so we
don't regress behavior that was already verified.
"""
from __future__ import annotations

from . import wuzzuf_collector


class WuzzufError(RuntimeError):
    pass


def fetch_jobs(query: str | None = None, location: str | None = None) -> list[dict]:
    """
    Returns a list of dicts matching JOB_FIELDS shape. wuzzuf_collector's
    WuzzufJob.as_dict() already matches the jobs table columns directly
    (it was built against this exact schema), so no remapping needed here.
    """
    try:
        jobs = wuzzuf_collector.collect()
        if not query and not location:
            return jobs

        query_terms = (query or "").lower().split()
        wanted_location = (location or "").lower().strip()

        def matches(job: dict) -> bool:
            searchable = " ".join(
                str(job.get(field) or "")
                for field in ("title", "company", "description", "category", "job_requirements")
            ).lower()
            location_value = str(job.get("area") or "").lower()
            return all(term in searchable for term in query_terms) and (
                not wanted_location or wanted_location in location_value
            )

        return [job for job in jobs if matches(job)]
    except Exception as exc:  # network, XML parse, etc.
        raise WuzzufError(f"wuzzuf_fetch_failed: {exc}") from exc
