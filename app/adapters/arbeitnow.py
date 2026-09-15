"""Arbeitnow public job-board API adapter."""
from __future__ import annotations

import os

import requests

from .base import normalize


ENDPOINT = "https://www.arbeitnow.com/api/job-board-api"


def fetch_jobs(query: str | None = None, location: str | None = None) -> list[dict]:
    response = requests.get(
        os.getenv("ARBEITNOW_ENDPOINT", ENDPOINT),
        params={"search": query or os.getenv("JOB_QUERY", ""), "page": 1},
        headers={"User-Agent": "JobSearchPlatform/1.0"},
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    jobs = []
    for item in payload.get("data", []):
        item_location = item.get("location") or "Remote"
        if location and location.lower() not in item_location.lower():
            continue
        tags = item.get("tags") or []
        jobs.append(normalize(
            source="arbeitnow",
            url=item.get("url", ""),
            title=item.get("title", ""),
            company=item.get("company_name", "Unknown"),
            description=item.get("description", ""),
            job_type=item.get("job_types", [None])[0] if item.get("job_types") else None,
            area=item_location,
            posted_at=item.get("created_at"),
            category=tags[0] if tags else None,
            extra={"arbeitnow_id": item.get("slug"), "tags": tags, "remote": item.get("remote", False)},
        ))
    return jobs
