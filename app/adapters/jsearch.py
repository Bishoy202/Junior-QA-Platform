"""JSearch API adapter through RapidAPI."""
from __future__ import annotations

import os

import requests

from .base import normalize


class JSearchError(RuntimeError):
    pass


def fetch_jobs(query: str | None = None, location: str | None = None) -> list[dict]:
    api_key = os.getenv("JSEARCH_RAPIDAPI_KEY")
    if not api_key:
        raise JSearchError("credentials_missing: set JSEARCH_RAPIDAPI_KEY")
    search_query = query or os.getenv("JOB_QUERY", "junior jobs entry level")
    if location:
        search_query = f"{search_query} in {location}"
    response = requests.get(
        os.getenv("JSEARCH_ENDPOINT", "https://jsearch.p.rapidapi.com/search"),
        headers={"X-RapidAPI-Key": api_key, "X-RapidAPI-Host": "jsearch.p.rapidapi.com"},
        params={"query": search_query, "page": 1, "num_pages": 1},
        timeout=20,
    )
    response.raise_for_status()
    jobs = []
    for item in response.json().get("data", []):
        jobs.append(normalize(
            source="jsearch",
            url=item.get("job_apply_link") or item.get("job_google_link", ""),
            title=item.get("job_title", ""),
            company=item.get("employer_name", "Unknown"),
            company_logo=item.get("employer_logo"),
            description=item.get("job_description", ""),
            salary=_format_salary(item),
            job_type=item.get("job_employment_type"),
            area=item.get("job_city") or item.get("job_country"),
            posted_at=item.get("job_posted_at_datetime_utc"),
            category=item.get("job_category"),
            extra={"jsearch_id": item.get("job_id"), "publisher": item.get("job_publisher")},
        ))
    return jobs


def _format_salary(item: dict) -> str | None:
    low, high = item.get("job_min_salary"), item.get("job_max_salary")
    if low and high:
        return f"{low}-{high} {item.get('job_salary_currency', '')}".strip()
    return None
