from pathlib import Path
from unittest.mock import patch

import requests

from app.adapters import wuzzuf_collector

FIXTURE = Path(__file__).parent / "fixtures" / "wuzzuf_sample.xml"


def test_parse_feed_returns_three_jobs():
    raw = FIXTURE.read_bytes()
    jobs = wuzzuf_collector.parse_feed(raw)
    assert len(jobs) == 3
    titles = {j.title for j in jobs}
    assert "Junior QA Engineer" in titles


def test_experience_with_no_digit_is_none():
    raw = FIXTURE.read_bytes()
    jobs = wuzzuf_collector.parse_feed(raw)
    marketing = next(j for j in jobs if j.title == "Marketing Specialist")
    assert marketing.experience is None


def test_external_id_is_stable_hash():
    url = "https://wuzzuf.net/jobs/p/aaa111-junior-qa-engineer"
    id1 = wuzzuf_collector._external_id_from_url(url)
    id2 = wuzzuf_collector._external_id_from_url(url)
    assert id1 == id2
    assert len(id1) == 40  # sha1 hex digest length


def test_fetch_jobs_matches_cairo_location_variants(monkeypatch):
    monkeypatch.setattr(wuzzuf_collector, "collect", lambda: [
        {"title": "QA Engineer", "company": "Example", "description": "Testing", "area": "New Cairo, Egypt", "category": "IT", "job_requirements": "", "url": "https://example.com/qa"},
    ])

    jobs = wuzzuf_collector.collect()
    from app.adapters import wuzzuf
    monkeypatch.setattr(wuzzuf_collector, "collect", lambda: jobs)
    assert len(wuzzuf.fetch_jobs(query="qa", location="Cairo")) == 1


def test_fetch_jobs_matches_cairo_when_area_is_missing(monkeypatch):
    monkeypatch.setattr(wuzzuf_collector, "collect", lambda: [
        {"title": "QA Engineer Cairo", "company": "Example", "description": "Testing", "area": None, "category": "IT", "job_requirements": "", "url": "https://example.com/cairo-qa"},
    ])

    from app.adapters import wuzzuf
    assert len(wuzzuf.fetch_jobs(query="qa", location="Cairo")) == 1


def test_collect_logs_and_returns_empty_list_on_request_failure():
    with patch(
        "requests.get",
        side_effect=requests.RequestException("blocked by network"),
    ):
        assert wuzzuf_collector.collect() == []


def test_fetch_response_uses_diagnostic_headers(monkeypatch):
    response = type("Response", (), {"status_code": 200})()
    with patch("requests.get", return_value=response) as request:
        wuzzuf_collector.fetch_response()

    headers = request.call_args.kwargs["headers"]
    assert headers["User-Agent"]
    assert "application/rss+xml" in headers["Accept"]
