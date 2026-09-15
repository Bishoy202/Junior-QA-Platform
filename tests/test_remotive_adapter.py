from unittest.mock import MagicMock, patch

from app.adapters import remotive


def test_fetch_jobs_parses_public_feed(monkeypatch):
    monkeypatch.setenv("REMOTIVE_CATEGORY", "software-dev")
    response = MagicMock()
    response.raise_for_status = lambda: None
    response.json.return_value = {
        "jobs": [
            {
                "id": 123,
                "url": "https://remotive.com/remote-jobs/software-dev/python-engineer",
                "title": "Junior Python Engineer",
                "company_name": "Remote Co",
                "company_logo": "https://example.com/logo.png",
                "description": "Build Python services and APIs.",
                "salary": "$50k-$70k",
                "job_type": "full_time",
                "candidate_required_location": "Worldwide",
                "publication_date": "2026-09-01T00:00:00",
                "category": "software-dev",
                "tags": ["python", "api"],
            }
        ]
    }

    with patch("requests.get", return_value=response) as request:
        jobs = remotive.fetch_jobs(query="python", location="worldwide")

    assert len(jobs) == 1
    job = jobs[0]
    assert job["source"] == "remotive"
    assert job["title"] == "Junior Python Engineer"
    assert job["company"] == "Remote Co"
    assert job["company_logo"] == "https://example.com/logo.png"
    assert job["area"] == "Worldwide"
    assert job["salary"] == "$50k-$70k"
    assert '"tags": ["python", "api"]' in job["extra_json"]
    request.assert_called_once()
    assert request.call_args.kwargs["params"]["search"] == "python"
    assert request.call_args.kwargs["params"]["category"] == "software-dev"


def test_fetch_jobs_filters_location(monkeypatch):
    response = MagicMock()
    response.raise_for_status = lambda: None
    response.json.return_value = {
        "jobs": [
            {
                "url": "https://example.com/1",
                "title": "Remote role",
                "company_name": "Company",
                "candidate_required_location": "United States",
            }
        ]
    }

    with patch("requests.get", return_value=response):
        assert remotive.fetch_jobs(location="Egypt") == []
