"""
app/adapters/base.py

Every adapter returns a list of plain dicts matching the `jobs` table's
column set. This module holds the shared normalize() helper so Adzuna and
Jooble records end up in the same shape as Wuzzuf's, instead of each
adapter inventing its own dict layout.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Optional

JOB_FIELDS = [
    "source", "external_id", "url", "title", "company", "company_url",
    "company_logo", "description", "salary", "experience", "vacancies",
    "category", "career_level", "job_requirements", "job_type", "area",
    "posted_at", "collected_at", "extra_json",
]


def stable_id(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize(
    *,
    source: str,
    url: str,
    title: str,
    company: str,
    description: str = "",
    salary: Optional[str] = None,
    job_type: Optional[str] = None,
    area: Optional[str] = None,
    posted_at: Optional[str] = None,
    company_url: Optional[str] = None,
    category: Optional[str] = None,
    extra: Optional[dict] = None,
) -> dict:
    """Build a normalized job dict shared across all adapters."""
    import json

    return {
        "source": source,
        "external_id": stable_id(url),
        "url": url,
        "title": title or "Untitled",
        "company": company or "Unknown",
        "company_url": company_url,
        "company_logo": None,
        "description": description or "",
        "salary": salary,
        "experience": None,
        "vacancies": None,
        "category": category,
        "career_level": None,
        "job_requirements": None,
        "job_type": job_type,
        "area": area,
        "posted_at": posted_at,
        "collected_at": now_iso(),
        "extra_json": json.dumps(extra or {}, ensure_ascii=False),
    }
