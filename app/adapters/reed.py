"""Reed.co.uk official API adapter."""
from __future__ import annotations

import os

import requests

from .base import normalize


class ReedError(RuntimeError):
    pass


def fetch_jobs(query: str | None = None, location: str | None = None) -> list[dict]:
    api_key = os.getenv("REED_API_KEY")
    if not api_key:
        raise ReedError("credentials_missing: set REED_API_KEY")
    response = requests.get(
        os.getenv("REED_ENDPOINT", "https://www.reed.co.uk/api/1.0/search"),
        auth=(api_key, ""),
        params={"keywords": query or os.getenv("JOB_QUERY", ""), "locationName": location or "", "resultsToTake": 100},
        timeout=20,
    )
    response.raise_for_status()
    jobs = []
    for item in response.json().get("results", []):
        jobs.append(normalize(
            source="reed",
            url=item.get("jobUrl", ""),
            title=item.get("jobTitle", ""),
            company=item.get("employerName", "Unknown"),
            description=item.get("jobDescription", ""),
            salary=_format_salary(item),
            area=item.get("locationName"),
            posted_at=item.get("date"),
            category=item.get("jobType"),
            extra={"reed_id": item.get("jobId"), "employer_id": item.get("employerId")},
        ))
    return jobs


def _format_salary(item: dict) -> str | None:
    low, high = item.get("minimumSalary"), item.get("maximumSalary")
    if low and high:
        return f"{low}-{high} {item.get('currency', '')}".strip()
    return None
