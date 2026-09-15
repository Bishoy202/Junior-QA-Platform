import os
import importlib


def test_health_and_sources(tmp_path, monkeypatch):
    db_path = str(tmp_path / "api_test.db")
    monkeypatch.setenv("DB_PATH", db_path)

    # Reimport so main.py picks up the patched DB_PATH at module load time.
    import app.main as main_module
    importlib.reload(main_module)

    from fastapi.testclient import TestClient
    client = TestClient(main_module.app)

    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

    r = client.get("/api/sources")
    body = r.json()
    assert "wuzzuf" in body["enabled"]
    assert "linkedin" in body["disabled"]
    assert "indeed" in body["disabled"]
    assert "glassdoor" in body["disabled"]

    r = client.get("/api/jobs")
    assert r.status_code == 200
    assert r.json()["jobs"] == []  # empty DB, no fabricated rows


def test_live_search_passes_query_and_location(tmp_path, monkeypatch):
    db_path = str(tmp_path / "search_test.db")
    monkeypatch.setenv("DB_PATH", db_path)

    import app.main as main_module
    importlib.reload(main_module)
    captured = {}

    def fake_pipeline(path, query=None, location=None):
        captured.update(path=path, query=query, location=location)
        return {"results": {}, "total_inserted": 0}

    monkeypatch.setattr(main_module, "run_pipeline", fake_pipeline)

    from fastapi.testclient import TestClient
    client = TestClient(main_module.app)
    response = client.post("/api/search?q=manual%20tester&location=Cairo")

    assert response.status_code == 200
    assert captured["query"] == "manual tester"
    assert captured["location"] == "Cairo"
