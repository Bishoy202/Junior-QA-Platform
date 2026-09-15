"""
wuzzuf_collector.py

Fetches Wuzzuf's official public "all jobs" RSS feed and normalizes each
listing into a plain dict ready for insertion into the platform's `jobs`
table.

Legitimate source: https://wuzzuf.net/feeds/all-jobs.xml
- Linked directly from Wuzzuf's own site footer (confirmed live).
- No login, API key, or authentication required -- unlike Bayt, which
  needs Google Custom Search credentials, this one works immediately.
- Wuzzuf's User Agreement restricts use of site material to personal,
  non-commercial, informational purposes and disallows redistribution --
  fine for a private tracker, not for re-publishing the feed itself.

This module does not touch LinkedIn, Indeed, or Glassdoor, and should not
be extended to. Those three stay fully disabled per project policy.
"""

from __future__ import annotations

import hashlib
import html
import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional

import requests

FEED_URL = "https://wuzzuf.net/feeds/all-jobs.xml"
SOURCE_NAME = "wuzzuf"
REQUEST_TIMEOUT = 15  # seconds
USER_AGENT = "JuniorQAJobPlatform/1.0 (+personal job tracker)"
LOGGER = logging.getLogger(__name__)

_HAS_DIGIT = re.compile(r"\d")


@dataclass
class WuzzufJob:
    source: str
    external_id: str
    url: str
    title: str
    company: str
    company_url: Optional[str]
    company_logo: Optional[str]
    description: str
    salary: Optional[str]
    experience: Optional[str]
    vacancies: Optional[str]
    category: Optional[str]
    career_level: Optional[str]
    job_requirements: Optional[str]
    job_type: Optional[str]
    area: Optional[str]
    posted_at: Optional[str]   # ISO 8601, UTC
    collected_at: str          # ISO 8601, UTC

    def as_dict(self) -> dict:
        return asdict(self)


def _text(item: ET.Element, tag: str) -> Optional[str]:
    """
    Stripped, HTML-unescaped text content of a child tag, or None if
    missing/blank. Wuzzuf's feed generator leaves literal entities like
    "&amp;" and "&nbsp;" sitting inside the CDATA text itself (confirmed
    against the live feed) rather than real "&"/space characters -- since
    CDATA content isn't re-parsed for entities, that's not something
    ElementTree resolves on its own, so it's unescaped here explicitly.
    """
    el = item.find(tag)
    if el is None or el.text is None:
        return None
    value = html.unescape(el.text).strip()
    return value or None


def _experience(item: ET.Element) -> Optional[str]:
    """
    Same as _text(), but Wuzzuf's own feed sometimes ships a value with no
    actual number in it (observed live: "<experience> years</experience>"
    with nothing before "years") -- treat that as unknown rather than
    storing a meaningless string.
    """
    value = _text(item, "experience")
    if value and not _HAS_DIGIT.search(value):
        return None
    return value


def _external_id_from_url(url: str) -> str:
    """
    Wuzzuf job URLs are usually /jobs/p/<uuid>-<slug>, but older listings
    use a short alphanumeric id instead of a UUID (confirmed against a
    real ~11-month-old listing) -- so don't assume a fixed id format.
    Hashing the full URL gives a stable, unique external_id regardless of
    which scheme Wuzzuf used for a given listing.
    """
    return hashlib.sha1(url.encode("utf-8")).hexdigest()


def _parse_pubdate(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError):
        return None


def fetch_response(timeout: int = REQUEST_TIMEOUT):
    """Fetch the raw Wuzzuf response for diagnostics and parsing."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
    }
    return requests.get(FEED_URL, headers=headers, timeout=timeout)


def fetch_raw_feed(timeout: int = REQUEST_TIMEOUT) -> bytes:
    """Fetch and validate the raw feed bytes."""
    response = fetch_response(timeout=timeout)
    response.raise_for_status()
    return response.content


def parse_feed(raw_xml: bytes) -> list[WuzzufJob]:
    """Parse raw RSS bytes into a list of normalized WuzzufJob records."""
    root = ET.fromstring(raw_xml)
    channel = root.find("channel")
    if channel is None:
        return []

    collected_at = datetime.now(timezone.utc).isoformat()
    jobs: list[WuzzufJob] = []

    for item in channel.findall("item"):
        url = _text(item, "link") or _text(item, "guid")
        if not url:
            continue  # nothing to dedupe or link back to -- skip

        source_el = item.find("source")
        company = None
        company_url = None
        if source_el is not None:
            company = html.unescape(source_el.text or "").strip() or None
            company_url = source_el.get("url")

        job = WuzzufJob(
            source=SOURCE_NAME,
            external_id=_external_id_from_url(url),
            url=url,
            title=_text(item, "title") or "Untitled",
            company=company or "Unknown",
            company_url=company_url,
            company_logo=_text(item, "source_logo"),
            description=_text(item, "description") or "",
            salary=_text(item, "salary"),
            experience=_experience(item),
            vacancies=_text(item, "vacancies"),
            category=_text(item, "roles"),
            career_level=_text(item, "career_level"),
            job_requirements=_text(item, "job_requirements"),
            job_type=_text(item, "job_type"),
            area=_text(item, "area"),
            posted_at=_parse_pubdate(_text(item, "pubDate")),
            collected_at=collected_at,
        )
        jobs.append(job)

    return jobs


def collect() -> list[dict]:
    """Fetch + parse in one call. Returns a list of plain dicts."""
    try:
        raw = fetch_raw_feed()
        return [job.as_dict() for job in parse_feed(raw)]
    except (requests.RequestException, ET.ParseError, ValueError) as exc:
        LOGGER.exception("Wuzzuf/Egypt feed failed: %s", exc)
        return []


if __name__ == "__main__":
    import json

    results = collect()
    print(f"Collected {len(results)} jobs from Wuzzuf.")
    if results:
        print(json.dumps(results[0], indent=2, ensure_ascii=False))
