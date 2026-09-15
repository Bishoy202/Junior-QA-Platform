"""
Direct test of the Adzuna adapter against a realistic mocked HTTP
response. This is deliberately separate from the pipeline tests (which
mock out the whole adapter function) -- this is the test that would
catch a broken normalize() call, a wrong field name, or a signature
mismatch, none of which the pipeline-level tests can see.
"""
from unittest.mock import patch, MagicMock

import pytest

from app.adapters import adzuna


def _fake_adzuna_response():
    resp = MagicMock()
    resp.raise_for_status = lambda: None
    resp.json.return_value = {
        "results": [
            {
                "id": "123",
                "redirect_url": "https://www.adzuna.co.uk/jobs/details/123",
                "title": "Junior QA Tester",
                "company": {"display_name": "TestCo"},
                "description": "manual testing role",
                "salary_min": 20000,
                "salary_max": 25000,
                "category": {"label": "IT Jobs"},
                "contract_time": "full_time",
                "location": {"display_name": "London"},
                "created": "2026-09-01T00:00:00Z",
            }
        ]
    }
    return resp


def test_fetch_jobs_requires_credentials(monkeypatch):
    monkeypatch.delenv("ADZUNA_APP_ID", raising=False)
    monkeypatch.delenv("ADZUNA_APP_KEY", raising=False)
    with pytest.raises(adzuna.AdzunaError, match="credentials_missing"):
        adzuna.fetch_jobs()


def test_fetch_jobs_rejects_unsupported_country(monkeypatch):
    monkeypatch.setenv("ADZUNA_APP_ID", "fake")
    monkeypatch.setenv("ADZUNA_APP_KEY", "fake")
    monkeypatch.setenv("ADZUNA_COUNTRY", "eg")
    with pytest.raises(adzuna.AdzunaError, match="unsupported_country"):
        adzuna.fetch_jobs()


def test_fetch_jobs_parses_real_response_shape(monkeypatch):
    """
    This is the test that catches a broken normalize() call. A version of
    this adapter that calls normalize() with wrong argument names or
    positionally instead of by keyword will raise here, not silently pass.
    """
    monkeypatch.setenv("ADZUNA_APP_ID", "fake")
    monkeypatch.setenv("ADZUNA_APP_KEY", "fake")
    monkeypatch.setenv("ADZUNA_COUNTRY", "gb")

    with patch("requests.get", return_value=_fake_adzuna_response()):
        jobs = adzuna.fetch_jobs()

    assert len(jobs) == 1
    job = jobs[0]
    assert job["source"] == "adzuna"
    assert job["title"] == "Junior QA Tester"
    assert job["company"] == "TestCo"
    assert job["url"] == "https://www.adzuna.co.uk/jobs/details/123"
    assert job["area"] == "London"
    assert "20000" in job["salary"] and "25000" in job["salary"]
    assert job["external_id"]  # computed by normalize(), must be non-empty
