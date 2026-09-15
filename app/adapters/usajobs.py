"""
Official USAJOBS API adapter.

Requires a free API key and a descriptive User-Agent from developer.usajobs.gov.
The API is limited to jobs in the United States.
"""
from __future__ import annotations

import os

import requests

from .base import normalize


class USAJobsError(RuntimeError):
    pass


def fetch_jobs(query: str | None = None, location: str | None = None) -> list[dict]:
    api_key = os.getenv("USAJOBS_API_KEY")
    user_agent = os.getenv("USAJOBS_USER_AGENT")
    if not api_key or not user_agent:
        raise USAJobsError(
            "credentials_missing: set USAJOBS_API_KEY and USAJOBS_USER_AGENT"
        )

    query = query or os.getenv("JOB_QUERY", "junior jobs entry level")
    location = location or os.getenv("USAJOBS_LOCATION", "")
    response = requests.get(
        os.getenv("USAJOBS_ENDPOINT", "https://data.usajobs.gov/api/search"),
        headers={
            "Authorization-Key": api_key,
            "User-Agent": user_agent,
        },
        params={
            "Keyword": query,
            "LocationName": location,
            "ResultsPerPage": 50,
        },
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()

    jobs = []
    for item in payload.get("SearchResult", {}).get("SearchResultItems", []):
        descriptor = item.get("MatchedObjectDescriptor", {})
        company = descriptor.get("OrganizationName") or ["U.S. Government"]
        location_data = descriptor.get("PositionLocation") or []
        areas = [entry.get("LocationName", "") for entry in location_data]
        details = descriptor.get("UserArea", {}).get("Details", {})
        url = descriptor.get("PositionURI") or item.get("MatchedObjectId", "")
        jobs.append(
            normalize(
                source="usajobs",
                url=url,
                title=descriptor.get("PositionTitle", ""),
                company=", ".join(company),
                description=descriptor.get("QualificationSummary", ""),
                area=", ".join(area for area in areas if area),
                posted_at=descriptor.get("PublicationStartDate"),
                category=descriptor.get("JobCategory", [{}])[0].get("Name") if descriptor.get("JobCategory") else None,
                job_type=details.get("JobType"),
                extra={
                    "usajobs_id": item.get("MatchedObjectId"),
                    "department": descriptor.get("DepartmentName"),
                    "agency": descriptor.get("OrganizationName"),
                },
            )
        )
    return jobs
