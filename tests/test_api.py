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
