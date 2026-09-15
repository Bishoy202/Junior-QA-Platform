"""
app/adapters/jooble.py

Official Jooble REST API. Requires a free API key from Jooble's API
portal (JOOBLE_API_KEY). Jooble uses country-specific API domains/keys,
so this Egypt-focused project defaults to the Egypt regional endpoint.
"""
from __future__ import annotations

import os
import requests

from .base import normalize


class JoobleError(RuntimeError):
    pass


def fetch_jobs(query: str | None = None, location: str | None = None) -> list[dict]:
    key = os.getenv("JOOBLE_API_KEY")
    if not key:
        raise JoobleError("credentials_missing: set JOOBLE_API_KEY")

    # Default to Egypt's regional endpoint so an Egypt-focused user cannot silently query the US pool.
    endpoint = os.getenv("JOOBLE_ENDPOINT", "https://eg.jooble.org/api")
    query = query or os.getenv(
        "JOB_QUERY", "junior QA tester quality assurance software testing"
    )
    location = location or os.getenv("JOOBLE_LOCATION", "Egypt")

    resp = requests.post(
        f"{endpoint.rstrip('/')}/{key}",
        json={
            "keywords": query,
            "location": location,
            "page": 1,
            "ResultOnPage": 50,
            "companysearch": False,
        },
        timeout=20,
    )
    resp.raise_for_status()
    payload = resp.json()

    jobs = []
    for item in payload.get("jobs", []):
        jobs.append(
            normalize(
                source="jooble",
                url=item.get("link", ""),
                title=item.get("title", ""),
                company=item.get("company") or "Unknown",
                description=item.get("snippet", ""),
                salary=item.get("salary") or None,
                job_type=item.get("type"),
                area=item.get("location"),
                posted_at=item.get("updated"),
                extra={"jooble_id": item.get("id")},
            )
        )
    return jobs
