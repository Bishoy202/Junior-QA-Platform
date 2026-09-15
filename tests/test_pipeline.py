from pathlib import Path

import pytest

from app import pipeline
from app.db import init_db, get_connection


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test_jobs.db")
    init_db(db_path)
    for source_name in pipeline.SOURCES:
        monkeypatch.setitem(pipeline.SOURCES, source_name, lambda: [])
    return db_path


def _fake_wuzzuf_jobs():
    fixture = Path(__file__).parent / "fixtures" / "wuzzuf_sample.xml"
    from app.adapters import wuzzuf_collector
    jobs = wuzzuf_collector.parse_feed(fixture.read_bytes())
    return [j.as_dict() for j in jobs]


def test_pipeline_inserts_and_scores_jobs(temp_db, monkeypatch):
    monkeypatch.setitem(pipeline.SOURCES, "wuzzuf", _fake_wuzzuf_jobs)
    monkeypatch.setitem(pipeline.SOURCES, "adzuna", lambda: (_ for _ in ()).throw(RuntimeError("credentials_missing")))
    monkeypatch.setitem(pipeline.SOURCES, "jooble", lambda: (_ for _ in ()).throw(RuntimeError("credentials_missing")))
    monkeypatch.setitem(pipeline.SOURCES, "usajobs", lambda: (_ for _ in ()).throw(RuntimeError("credentials_missing")))
    monkeypatch.setitem(pipeline.SOURCES, "remotive", lambda: [])

    result = pipeline.run_pipeline(temp_db)

    assert result["results"]["wuzzuf"]["status"] == "ok"
    assert result["results"]["wuzzuf"]["inserted"] == 3
    assert result["results"]["adzuna"]["status"] == "error"
    assert result["results"]["jooble"]["status"] == "error"
    assert result["results"]["linkedin"]["status"] == "disabled"

    conn = get_connection(temp_db)
    rows = conn.execute("SELECT * FROM jobs").fetchall()
    assert len(rows) == 3
    junior = next(r for r in rows if r["title"] == "Junior QA Engineer")
    assert junior["fit_score"] >= 0.7
    conn.close()


def test_pipeline_second_run_deduplicates(temp_db, monkeypatch):
    monkeypatch.setitem(pipeline.SOURCES, "wuzzuf", _fake_wuzzuf_jobs)
    monkeypatch.setitem(pipeline.SOURCES, "adzuna", lambda: [])
    monkeypatch.setitem(pipeline.SOURCES, "jooble", lambda: [])
    monkeypatch.setitem(pipeline.SOURCES, "usajobs", lambda: [])
    monkeypatch.setitem(pipeline.SOURCES, "remotive", lambda: [])

    first = pipeline.run_pipeline(temp_db)
    second = pipeline.run_pipeline(temp_db)

    assert first["results"]["wuzzuf"]["inserted"] == 3
    assert second["results"]["wuzzuf"]["inserted"] == 0  # all duplicates, same URLs

    conn = get_connection(temp_db)
    count = conn.execute("SELECT COUNT(*) c FROM jobs").fetchone()["c"]
    assert count == 3
    conn.close()


def test_one_source_failure_does_not_block_others(temp_db, monkeypatch):
    monkeypatch.setitem(pipeline.SOURCES, "wuzzuf", lambda: (_ for _ in ()).throw(RuntimeError("dns failure")))
    monkeypatch.setitem(pipeline.SOURCES, "adzuna", lambda: (_ for _ in ()).throw(RuntimeError("credentials_missing")))
    monkeypatch.setitem(pipeline.SOURCES, "jooble", _fake_wuzzuf_jobs)  # stand-in payload, just testing isolation
    monkeypatch.setitem(pipeline.SOURCES, "usajobs", lambda: [])
    monkeypatch.setitem(pipeline.SOURCES, "remotive", lambda: [])

    result = pipeline.run_pipeline(temp_db)

    assert result["results"]["wuzzuf"]["status"] == "error"
    assert result["results"]["jooble"]["status"] == "ok"
    assert result["results"]["jooble"]["inserted"] == 3


def test_pipeline_passes_live_search_terms_to_sources(temp_db, monkeypatch):
    calls = []

    def fake_source(query=None, location=None):
        calls.append((query, location))
        return []

    monkeypatch.setitem(pipeline.SOURCES, "wuzzuf", fake_source)
    monkeypatch.setitem(pipeline.SOURCES, "adzuna", fake_source)
    monkeypatch.setitem(pipeline.SOURCES, "jooble", fake_source)
    monkeypatch.setitem(pipeline.SOURCES, "usajobs", fake_source)
    monkeypatch.setitem(pipeline.SOURCES, "remotive", fake_source)
    monkeypatch.setitem(pipeline.SOURCES, "remoteok", fake_source)
    monkeypatch.setitem(pipeline.SOURCES, "arbeitnow", fake_source)
    monkeypatch.setitem(pipeline.SOURCES, "reed", fake_source)
    monkeypatch.setitem(pipeline.SOURCES, "jsearch", fake_source)
    monkeypatch.setitem(pipeline.SOURCES, "serpapi", fake_source)
    monkeypatch.setitem(pipeline.SOURCES, "jobspipe", fake_source)

    pipeline.run_pipeline(temp_db, query="manual tester", location="Cairo")

    assert calls == [("manual tester", "Cairo")] * len(pipeline.SOURCES)


def test_refresh_clears_untracked_jobs_but_preserves_saved_jobs(temp_db, monkeypatch):
    conn = get_connection(temp_db)
    for external_id in ("old-1", "old-2"):
        conn.execute(
            "INSERT INTO jobs (source, external_id, url, title, company, description, collected_at, fit_score, fit_reasons, extra_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("remotive", external_id, f"https://example.com/{external_id}", external_id, "Company", "Role", "2024-01-01T00:00:00Z", 0.5, "[]", "{}"),
        )
    saved_job_id = conn.execute("SELECT id FROM jobs WHERE external_id = ?", ("old-1",)).fetchone()[0]
    conn.execute(
        "INSERT INTO applications (job_id, status, updated_at) VALUES (?, ?, ?)",
        (saved_job_id, "saved", "2024-01-01T00:00:00Z"),
    )
    conn.commit()
    conn.close()
    for source_name in pipeline.SOURCES:
        monkeypatch.setitem(pipeline.SOURCES, source_name, lambda: [])

    result = pipeline.run_pipeline(temp_db, clear_existing=True)

    assert result["total_cleared"] == 1
    conn = get_connection(temp_db)
    rows = conn.execute("SELECT external_id FROM jobs ORDER BY external_id").fetchall()
    assert [row["external_id"] for row in rows] == ["old-1"]
    conn.close()
