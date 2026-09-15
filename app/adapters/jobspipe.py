"""Configurable LoopCV/JobsPipe adapter.

JobsPipe deployments expose different URLs and payload wrappers, so the
endpoint is intentionally configured by the user rather than guessed.
"""
from __future__ import annotations

import os

import requests

from .base import normalize


class JobsPipeError(RuntimeError):
    pass


def fetch_jobs(query: str | None = None, location: str | None = None) -> list[dict]:
    endpoint = os.getenv("JOBSPIPE_ENDPOINT") or os.getenv("LOOPCV_ENDPOINT")
    api_key = os.getenv("JOBSPIPE_API_KEY") or os.getenv("LOOPCV_API_KEY")
    if not endpoint:
        raise JobsPipeError("configuration_missing: set JOBSPIPE_ENDPOINT or LOOPCV_ENDPOINT")
    params = {"query": query or os.getenv("JOB_QUERY", ""), "location": location or ""}
    headers = {"User-Agent": "JobSearchPlatform/1.0"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    response = requests.get(endpoint, params=params, headers=headers, timeout=20)
    response.raise_for_status()
    payload = response.json()
    items = payload if isinstance(payload, list) else payload.get("jobs") or payload.get("data") or payload.get("results") or []
    jobs = []
    for item in items:
        if not isinstance(item, dict):
            continue
        jobs.append(normalize(
            source="jobspipe",
            url=item.get("url") or item.get("job_url") or item.get("link", ""),
            title=item.get("title") or item.get("job_title", ""),
            company=item.get("company") or item.get("company_name", "Unknown"),
            description=item.get("description") or item.get("job_description", ""),
            area=item.get("location") or item.get("candidate_required_location"),
            posted_at=item.get("posted_at") or item.get("publication_date"),
            category=item.get("category"),
            extra={"jobspipe_id": item.get("id") or item.get("job_id")},
        ))
    return jobs
