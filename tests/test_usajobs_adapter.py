from unittest.mock import MagicMock, patch

import pytest

from app.adapters import usajobs


def _fake_response():
    response = MagicMock()
    response.raise_for_status = lambda: None
    response.json.return_value = {
        "SearchResult": {
            "SearchResultItems": [
                {
                    "MatchedObjectId": "123",
                    "MatchedObjectDescriptor": {
                        "PositionTitle": "Junior Software Analyst",
                        "PositionURI": "https://www.usajobs.gov/job/123",
                        "OrganizationName": ["Department of Testing"],
                        "DepartmentName": "Example Agency",
                        "QualificationSummary": "Uses Python and SQL to test software.",
                        "PositionLocation": [{"LocationName": "Washington, DC"}],
                        "PublicationStartDate": "2026-09-01",
                        "JobCategory": [{"Name": "Information Technology"}],
                        "UserArea": {"Details": {"JobType": "Full-time"}},
                    },
                }
            ]
        }
    }
    return response


def test_fetch_jobs_requires_credentials(monkeypatch):
    monkeypatch.delenv("USAJOBS_API_KEY", raising=False)
    monkeypatch.delenv("USAJOBS_USER_AGENT", raising=False)
    with pytest.raises(usajobs.USAJobsError, match="credentials_missing"):
        usajobs.fetch_jobs()


def test_fetch_jobs_parses_official_response(monkeypatch):
    monkeypatch.setenv("USAJOBS_API_KEY", "fake-key")
    monkeypatch.setenv("USAJOBS_USER_AGENT", "test@example.com")

    with patch("requests.get", return_value=_fake_response()) as request:
        jobs = usajobs.fetch_jobs(query="software", location="Washington")

    assert len(jobs) == 1
    job = jobs[0]
    assert job["source"] == "usajobs"
    assert job["title"] == "Junior Software Analyst"
    assert job["company"] == "Department of Testing"
    assert job["area"] == "Washington, DC"
    assert job["category"] == "Information Technology"
    assert job["job_type"] == "Full-time"
    assert job["external_id"]
    request.assert_called_once()
    assert request.call_args.kwargs["headers"]["Authorization-Key"] == "fake-key"
    assert request.call_args.kwargs["headers"]["User-Agent"] == "test@example.com"
    assert request.call_args.kwargs["params"]["Keyword"] == "software"
