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


def fetch_jobs() -> list[dict]:
    """
    Returns a list of dicts matching JOB_FIELDS shape. wuzzuf_collector's
    WuzzufJob.as_dict() already matches the jobs table columns directly
    (it was built against this exact schema), so no remapping needed here.
    """
    try:
        return wuzzuf_collector.collect()
    except Exception as exc:  # network, XML parse, etc.
        raise WuzzufError(f"wuzzuf_fetch_failed: {exc}") from exc
