"""
Official Remotive public JSON feed adapter.

Remotive does not require an API key. It provides remote jobs and supports
optional category/search filters through the public feed.
"""
from __future__ import annotations

import os

import requests

from .base import normalize


REMOTIVE_ENDPOINT = "https://remotive.com/api/remote-jobs"


def fetch_jobs(query: str | None = None, location: str | None = None) -> list[dict]:
    query = query or os.getenv("JOB_QUERY", "junior jobs entry level")
    category = os.getenv("REMOTIVE_CATEGORY", "")
    params = {"limit": 50}
    if query:
        params["search"] = query
    if category:
        params["category"] = category

    response = requests.get(
        os.getenv("REMOTIVE_ENDPOINT", REMOTIVE_ENDPOINT),
        params=params,
        headers={"User-Agent": "JobSearchPlatform/1.0"},
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()

    jobs = []
    for item in payload.get("jobs", []):
        candidate_location = item.get("candidate_required_location") or "Remote"
        if location and location.lower() not in candidate_location.lower():
            continue
        tags = item.get("tags") or []
        jobs.append(
            normalize(
                source="remotive",
                url=item.get("url", ""),
                title=item.get("title", ""),
                company=item.get("company_name", "Unknown"),
                company_logo=item.get("company_logo"),
                description=item.get("description", ""),
                salary=item.get("salary") or None,
                job_type=item.get("job_type"),
                area=candidate_location,
                posted_at=item.get("publication_date"),
                category=item.get("category"),
                extra={
                    "remotive_id": item.get("id"),
                    "tags": tags,
                },
            )
        )
    return jobs
