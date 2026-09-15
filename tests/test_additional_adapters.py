from unittest.mock import MagicMock, patch

import pytest

from app.adapters import arbeitnow, jobspipe, jsearch, reed, remoteok, serpapi


def response(payload):
    result = MagicMock()
    result.raise_for_status = lambda: None
    result.json.return_value = payload
    return result


def test_remoteok_parses_public_feed():
    payload = [{"legal": "public"}, {"id": 1, "url": "https://remoteok.com/1", "position": "Python Developer", "company": "Remote Co", "description": "Python APIs", "tags": ["python"], "location": "Worldwide"}]
    with patch("requests.get", return_value=response(payload)):
        jobs = remoteok.fetch_jobs(query="python", location="worldwide")
    assert jobs[0]["source"] == "remoteok"
    assert jobs[0]["title"] == "Python Developer"


def test_arbeitnow_parses_public_feed():
    payload = {"data": [{"slug": "one", "url": "https://arbeitnow.com/1", "title": "QA Tester", "company_name": "Work Co", "description": "Testing", "location": "Remote", "tags": ["qa"]}]}
    with patch("requests.get", return_value=response(payload)):
        jobs = arbeitnow.fetch_jobs(query="qa", location="remote")
    assert jobs[0]["source"] == "arbeitnow"
    assert jobs[0]["company"] == "Work Co"


def test_reed_requires_key_and_parses_results(monkeypatch):
    monkeypatch.setenv("REED_API_KEY", "key")
    payload = {"results": [{"jobId": 2, "jobUrl": "https://reed.co.uk/2", "jobTitle": "Analyst", "employerName": "Reed Co", "jobDescription": "Work", "locationName": "London"}]}
    with patch("requests.get", return_value=response(payload)):
        jobs = reed.fetch_jobs(query="analyst", location="London")
    assert jobs[0]["source"] == "reed"
    assert jobs[0]["company"] == "Reed Co"


def test_jsearch_parses_rapidapi_results(monkeypatch):
    monkeypatch.setenv("JSEARCH_RAPIDAPI_KEY", "key")
    payload = {"data": [{"job_id": "j1", "job_apply_link": "https://example.com/apply", "job_title": "Developer", "employer_name": "J Co", "job_description": "Build", "job_city": "London"}]}
    with patch("requests.get", return_value=response(payload)):
        jobs = jsearch.fetch_jobs(query="developer", location="London")
    assert jobs[0]["source"] == "jsearch"
    assert jobs[0]["url"] == "https://example.com/apply"


def test_serpapi_parses_google_jobs(monkeypatch):
    monkeypatch.setenv("SERPAPI_API_KEY", "key")
    payload = {"jobs_results": [{"job_id": "s1", "title": "Engineer", "company_name": "Google Jobs Co", "location": "Remote", "apply_options": [{"link": "https://example.com/apply"}]}]}
    with patch("requests.get", return_value=response(payload)):
        jobs = serpapi.fetch_jobs(query="engineer", location="Remote")
    assert jobs[0]["source"] == "serpapi"
    assert jobs[0]["url"] == "https://example.com/apply"


def test_jobspipe_supports_configured_endpoint(monkeypatch):
    monkeypatch.setenv("JOBSPIPE_ENDPOINT", "https://jobs.example/api")
    payload = {"data": [{"id": "p1", "url": "https://example.com/job", "title": "Support", "company_name": "Pipe Co", "description": "Help users"}]}
    with patch("requests.get", return_value=response(payload)):
        jobs = jobspipe.fetch_jobs(query="support")
    assert jobs[0]["source"] == "jobspipe"
    assert jobs[0]["company"] == "Pipe Co"


def test_credentialed_adapters_fail_clearly_without_keys(monkeypatch):
    for variable, adapter in (("REED_API_KEY", reed), ("JSEARCH_RAPIDAPI_KEY", jsearch), ("SERPAPI_API_KEY", serpapi)):
        monkeypatch.delenv(variable, raising=False)
        with pytest.raises(RuntimeError, match="credentials_missing"):
            adapter.fetch_jobs()
