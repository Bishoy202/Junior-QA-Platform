"""
app/adapters/adzuna.py

Official Adzuna REST API. Requires free credentials from
developer.adzuna.com (ADZUNA_APP_ID, ADZUNA_APP_KEY).

Adzuna very likely does not cover Egypt: no single official page lists
every supported country, but several independent implementations built
against Adzuna's real API (an SDK, an MCP server, a scraper spec) all
list the same ~12-19 markets, and none of them include Egypt. That's
convergent evidence, not one canonical source -- worth re-checking if
Adzuna ever publishes a definitive list. This adapter is for
supplementary international/remote roles, not a substitute for Wuzzuf's
local coverage. Requesting an unsupported country code raises here rather
than silently sending a request Adzuna would reject anyway.
"""
from __future__ import annotations

import os
import requests

from .base import normalize

# Countries Adzuna is confirmed to operate in (ISO 3166-1 alpha-2).
# Egypt ("eg") is deliberately absent.
SUPPORTED_COUNTRIES = {
    "gb", "us", "de", "fr", "au", "nz", "ca", "in", "pl", "br", "at", "za",
    "nl", "it", "es", "ch", "sg", "mx", "be",
}


class AdzunaError(RuntimeError):
    pass


def fetch_jobs(query: str | None = None, location: str | None = None) -> list[dict]:
    app_id = os.getenv("ADZUNA_APP_ID")
    app_key = os.getenv("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        raise AdzunaError("credentials_missing: set ADZUNA_APP_ID and ADZUNA_APP_KEY")

    country = os.getenv("ADZUNA_COUNTRY", "gb").lower()
    if country not in SUPPORTED_COUNTRIES:
        raise AdzunaError(
            f"unsupported_country: Adzuna does not operate in '{country}'. "
            f"Supported: {sorted(SUPPORTED_COUNTRIES)}"
        )

    query = query or os.getenv(
        "JOB_QUERY", "junior QA tester quality assurance software testing"
    )
    location = location or os.getenv("ADZUNA_LOCATION", "")

    url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/1"
    resp = requests.get(
        url,
        params={
            "app_id": app_id,
            "app_key": app_key,
            "results_per_page": 50,
            "what": query,
            "where": location,
            "content-type": "application/json",
        },
        timeout=20,
    )
    resp.raise_for_status()
    payload = resp.json()

    jobs = []
    for item in payload.get("results", []):
        jobs.append(
            normalize(
                source="adzuna",
                url=item.get("redirect_url") or item.get("id", ""),
                title=item.get("title", ""),
                company=(item.get("company") or {}).get("display_name", "Unknown"),
                description=item.get("description", ""),
                salary=_format_salary(item),
                job_type=item.get("contract_time"),
                area=(item.get("location") or {}).get("display_name"),
                posted_at=item.get("created"),
                category=(item.get("category") or {}).get("label"),
                extra={"adzuna_id": item.get("id"), "country": country},
            )
        )
    return jobs


def _format_salary(item: dict) -> str | None:
    lo, hi = item.get("salary_min"), item.get("salary_max")
    if lo and hi:
        return f"{lo:.0f}-{hi:.0f}"
    return None
