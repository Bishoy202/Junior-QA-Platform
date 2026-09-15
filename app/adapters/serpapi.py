"""SerpApi Google Jobs adapter."""
from __future__ import annotations

import os

import requests

from .base import normalize


class SerpApiError(RuntimeError):
    pass


def fetch_jobs(query: str | None = None, location: str | None = None) -> list[dict]:
    api_key = os.getenv("SERPAPI_API_KEY")
    if not api_key:
        raise SerpApiError("credentials_missing: set SERPAPI_API_KEY")
    response = requests.get(
        os.getenv("SERPAPI_ENDPOINT", "https://serpapi.com/search.json"),
        params={"engine": "google_jobs", "q": query or os.getenv("JOB_QUERY", "junior jobs"), "location": location or "", "api_key": api_key},
        timeout=20,
    )
    response.raise_for_status()
    jobs = []
    for item in response.json().get("jobs_results", []):
        apply_options = item.get("apply_options") or []
        url = apply_options[0].get("link", "") if apply_options else item.get("share_link", "")
        jobs.append(normalize(
            source="serpapi",
            url=url,
            title=item.get("title", ""),
            company=item.get("company_name", "Unknown"),
            description=item.get("description", ""),
            area=item.get("location"),
            posted_at=item.get("detected_extensions", {}).get("posted_at"),
            category=item.get("via"),
            extra={"serpapi_id": item.get("job_id"), "extensions": item.get("detected_extensions", {}), "tags": item.get("extensions", [])},
        ))
    return jobs
