"""Remote OK public JSON feed adapter."""
from __future__ import annotations

import os

import requests

from .base import normalize


ENDPOINT = "https://remoteok.com/api"


def fetch_jobs(query: str | None = None, location: str | None = None) -> list[dict]:
    response = requests.get(
        os.getenv("REMOTEOK_ENDPOINT", ENDPOINT),
        headers={"User-Agent": "JobSearchPlatform/1.0"},
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    jobs = []
    query_terms = (query or os.getenv("JOB_QUERY", "")).lower().split()
    for item in payload[1:] if payload and isinstance(payload[0], dict) and "legal" in payload[0] else payload:
        if not isinstance(item, dict) or not item.get("url"):
            continue
        text = " ".join(str(item.get(field) or "") for field in ("position", "description", "tags")).lower()
        if query_terms and not all(term in text for term in query_terms):
            continue
        item_location = item.get("location") or "Remote"
        if location and location.lower() not in item_location.lower():
            continue
        jobs.append(normalize(
            source="remoteok",
            url=item["url"],
            title=item.get("position", ""),
            company=item.get("company", "Unknown"),
            company_logo=item.get("company_logo"),
            description=item.get("description", ""),
            salary=_format_salary(item),
            job_type=item.get("job_type"),
            area=item_location,
            posted_at=item.get("date") or item.get("epoch"),
            category=item.get("tags", [None])[0] if item.get("tags") else None,
            extra={"remoteok_id": item.get("id"), "tags": item.get("tags", [])},
        ))
    return jobs


def _format_salary(item: dict) -> str | None:
    low, high = item.get("salary_min"), item.get("salary_max")
    if low and high:
        return f"{low}-{high}"
    return item.get("salary") or None
