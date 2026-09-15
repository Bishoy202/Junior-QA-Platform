from pathlib import Path

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
