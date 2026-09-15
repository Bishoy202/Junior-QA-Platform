"""
Direct test of the Jooble adapter against a realistic mocked HTTP
response. This is deliberately separate from the pipeline tests (which
mock out the whole adapter function) -- this is the test that catches a
broken normalize() call, a wrong field name, or a signature mismatch.
"""
from unittest.mock import patch, MagicMock

import pytest

from app.adapters import jooble


def _fake_jooble_response():
    resp = MagicMock()
    resp.raise_for_status = lambda: None
    resp.json.return_value = {
        "totalCount": 1,
        "jobs": [
            {
                "id": 1234567890,
                "title": "Sales Manager",
                "location": "Kyiv",
                "snippet": "This is a great opportunity...",
                "salary": "17,600 UAH",
                "source": "jooble",
                "type": "Full-time",
                "link": "https://ua.jooble.org/jdp/12345",
                "company": "ABC Corp",
                "updated": "2023-09-15T12:55:35.3870000",
            }
        ],
    }
    return resp


def test_fetch_jobs_requires_credentials(monkeypatch):
    monkeypatch.delenv("JOOBLE_API_KEY", raising=False)

    with pytest.raises(jooble.JoobleError, match="credentials_missing"):
        jooble.fetch_jobs()


def test_fetch_jobs_parses_real_response_shape(monkeypatch):
    monkeypatch.setenv("JOOBLE_API_KEY", "fake")
    monkeypatch.setenv("JOOBLE_ENDPOINT", "https://eg.jooble.org/api")

    with patch("requests.post", return_value=_fake_jooble_response()):
        jobs = jooble.fetch_jobs()

    assert len(jobs) == 1

    job = jobs[0]

    assert job["source"] == "jooble"
    assert job["title"] == "Sales Manager"
    assert job["company"] == "ABC Corp"
    assert job["url"] == "https://ua.jooble.org/jdp/12345"
    assert job["area"] == "Kyiv"
    assert job["salary"] == "17,600 UAH"
    assert job["job_type"] == "Full-time"
    assert job["posted_at"] == "2023-09-15T12:55:35.3870000"
    assert job["external_id"]

    assert '"jooble_id": 1234567890' in job["extra_json"]
