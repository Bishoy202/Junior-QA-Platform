from pathlib import Path

import pytest

from app import pipeline
from app.db import init_db, get_connection


@pytest.fixture
def temp_db(tmp_path):
    db_path = str(tmp_path / "test_jobs.db")
    init_db(db_path)
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

    result = pipeline.run_pipeline(temp_db)

    assert result["results"]["wuzzuf"]["status"] == "error"
    assert result["results"]["jooble"]["status"] == "ok"
    assert result["results"]["jooble"]["inserted"] == 3
