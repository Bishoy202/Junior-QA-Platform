import os
import importlib
import asyncio


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


def test_startup_ingestion_failure_does_not_escape(tmp_path, monkeypatch):
    db_path = str(tmp_path / "startup_failure_test.db")
    monkeypatch.setenv("DB_PATH", db_path)
    monkeypatch.setenv("AUTO_INGEST_ON_STARTUP", "true")

    import app.main as main_module
    importlib.reload(main_module)

    def failing_pipeline(*args, **kwargs):
        raise RuntimeError("adapter unavailable")

    monkeypatch.setattr(main_module, "run_pipeline", failing_pipeline)
    asyncio.run(main_module.run_startup_ingestion())


def test_startup_ingestion_skips_populated_database(tmp_path, monkeypatch):
    db_path = str(tmp_path / "startup_populated_test.db")
    monkeypatch.setenv("DB_PATH", db_path)
    monkeypatch.setenv("AUTO_INGEST_ON_STARTUP", "true")

    import app.main as main_module
    importlib.reload(main_module)
    conn = main_module.get_connection(db_path)
    conn.execute(
        "INSERT INTO jobs (source, external_id, url, title, company, description, collected_at, fit_score, fit_reasons, extra_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("wuzzuf", "startup-job", "https://example.com/startup", "Existing job", "Company", "Role", "2024-01-01T00:00:00Z", 0.5, "[]", "{}"),
    )
    conn.commit()
    conn.close()

    called = False

    def unexpected_pipeline(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(main_module, "run_pipeline", unexpected_pipeline)
    asyncio.run(main_module.run_startup_ingestion())

    assert called is False


def test_jobs_can_be_filtered_by_source(tmp_path, monkeypatch):
    db_path = str(tmp_path / "source_filter_test.db")
    monkeypatch.setenv("DB_PATH", db_path)

    import app.main as main_module
    importlib.reload(main_module)

    conn = main_module.get_connection(db_path)
    for source, external_id in (("wuzzuf", "w1"), ("adzuna", "a1")):
        conn.execute(
            "INSERT INTO jobs (source, external_id, url, title, company, description, collected_at, fit_score, fit_reasons, extra_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (source, external_id, f"https://example.com/{external_id}", "QA role", "Company", "Testing", "2024-01-01T00:00:00Z", 0.5, "[]", "{}"),
        )
    conn.commit()
    conn.close()

    from fastapi.testclient import TestClient
    client = TestClient(main_module.app)
    response = client.get("/api/jobs?source=adzuna")

    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert response.json()["jobs"][0]["source"] == "adzuna"


def test_jobs_can_be_filtered_by_work_mode(tmp_path, monkeypatch):
    db_path = str(tmp_path / "work_mode_filter_test.db")
    monkeypatch.setenv("DB_PATH", db_path)

    import app.main as main_module
    importlib.reload(main_module)
    conn = main_module.get_connection(db_path)
    for external_id, description in (("remote", "Fully remote QA role"), ("office", "On-site QA role")):
        conn.execute(
            "INSERT INTO jobs (source, external_id, url, title, company, description, collected_at, fit_score, fit_reasons, extra_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("wuzzuf", external_id, f"https://example.com/{external_id}", "QA role", "Company", description, "2024-01-01T00:00:00Z", 0.5, "[]", "{}"),
        )
    conn.commit()
    conn.close()

    from fastapi.testclient import TestClient
    client = TestClient(main_module.app)
    response = client.get("/api/jobs?work_mode=remote")

    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert response.json()["jobs"][0]["external_id"] == "remote"


def test_jobs_include_detected_work_mode(tmp_path, monkeypatch):
    db_path = str(tmp_path / "work_mode_label_test.db")
    monkeypatch.setenv("DB_PATH", db_path)

    import app.main as main_module
    importlib.reload(main_module)
    conn = main_module.get_connection(db_path)
    conn.execute(
        "INSERT INTO jobs (source, external_id, url, title, company, description, collected_at, fit_score, fit_reasons, extra_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("wuzzuf", "hybrid", "https://example.com/hybrid", "QA Engineer", "Company", "Hybrid role", "2024-01-01T00:00:00Z", 0.5, "[]", "{}"),
    )
    conn.commit()
    conn.close()

    from fastapi.testclient import TestClient
    job = TestClient(main_module.app).get("/api/jobs").json()["jobs"][0]
    assert job["work_mode"] == "hybrid"


def test_live_search_passes_query_and_location(tmp_path, monkeypatch):
    db_path = str(tmp_path / "search_test.db")
    monkeypatch.setenv("DB_PATH", db_path)

    import app.main as main_module
    importlib.reload(main_module)
    captured = {}

    def fake_pipeline(path, query=None, location=None, source=None, work_mode=None):
        captured.update(path=path, query=query, location=location, source=source, work_mode=work_mode)
        return {"results": {}, "total_inserted": 0}

    monkeypatch.setattr(main_module, "run_pipeline", fake_pipeline)

    from fastapi.testclient import TestClient
    client = TestClient(main_module.app)
    response = client.post("/api/search?q=manual%20tester&location=Cairo")

    assert response.status_code == 200
    assert captured["query"] == "manual tester"
    assert captured["location"] == "Cairo"


def test_live_search_can_run_selected_source_without_keyword(tmp_path, monkeypatch):
    db_path = str(tmp_path / "source_search_test.db")
    monkeypatch.setenv("DB_PATH", db_path)

    import app.main as main_module
    importlib.reload(main_module)
    captured = {}

    def fake_pipeline(path, query=None, location=None, source=None, work_mode=None):
        captured.update(query=query, location=location, source=source, work_mode=work_mode)
        return {"results": {source: {"status": "ok"}}, "total_inserted": 0}

    monkeypatch.setattr(main_module, "run_pipeline", fake_pipeline)

    from fastapi.testclient import TestClient
    client = TestClient(main_module.app)
    response = client.post("/api/search?location=Cairo&source=usajobs")

    assert response.status_code == 200
    assert captured == {"query": None, "location": "Cairo", "source": "usajobs", "work_mode": None}


def test_live_search_forwards_all_filters(tmp_path, monkeypatch):
    db_path = str(tmp_path / "all_filters_search_test.db")
    monkeypatch.setenv("DB_PATH", db_path)

    import app.main as main_module
    importlib.reload(main_module)
    captured = {}

    def fake_pipeline(path, query=None, location=None, source=None, work_mode=None):
        captured.update(query=query, location=location, source=source, work_mode=work_mode)
        return {"results": {}, "total_inserted": 0}

    monkeypatch.setattr(main_module, "run_pipeline", fake_pipeline)

    from fastapi.testclient import TestClient
    response = TestClient(main_module.app).post(
        "/api/search?q=qa&location=Cairo&source=wuzzuf&work_mode=hybrid"
    )

    assert response.status_code == 200
    assert captured == {
        "query": "qa",
        "location": "Cairo",
        "source": "wuzzuf",
        "work_mode": "hybrid",
    }


def test_live_search_corrects_common_job_and_location_typos(tmp_path, monkeypatch):
    db_path = str(tmp_path / "search_correction_test.db")
    monkeypatch.setenv("DB_PATH", db_path)

    import app.main as main_module
    importlib.reload(main_module)
    captured = {}

    def fake_pipeline(path, query=None, location=None, source=None, work_mode=None):
        captured.update(query=query, location=location, source=source, work_mode=work_mode)
        return {"results": {}, "total_inserted": 0}

    monkeypatch.setattr(main_module, "run_pipeline", fake_pipeline)

    from fastapi.testclient import TestClient
    client = TestClient(main_module.app)
    response = client.post("/api/search?q=pythn%20develper&location=Cairoo")

    assert response.status_code == 200
    assert response.json()["query"] == "python developer"
    assert response.json()["location"] == "cairo"
    assert captured == {"query": "python developer", "location": "cairo", "source": None, "work_mode": None}


def test_cv_upload_personalizes_job_score(tmp_path, monkeypatch):
    db_path = str(tmp_path / "cv_test.db")
    monkeypatch.setenv("DB_PATH", db_path)

    import app.main as main_module
    importlib.reload(main_module)

    from fastapi.testclient import TestClient
    client = TestClient(main_module.app)
    conn = main_module.get_connection(db_path)
    conn.execute(
        "INSERT INTO jobs (source, external_id, url, title, company, description, category, collected_at, fit_score, fit_reasons, extra_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("wuzzuf", "job-1", "https://example.com/1", "Python Developer", "Acme", "Build Python APIs", "Engineering", "2024-01-01T00:00:00Z", 0.25, "[]", "{}"),
    )
    conn.commit()
    conn.close()

    upload = client.post(
        "/api/cv",
        files={"file": ("resume.txt", b"Python developer with API testing and SQL experience.", "text/plain")},
    )

    assert upload.status_code == 200
    jobs = client.get("/api/jobs").json()
    assert jobs["cv_loaded"] is True
    assert jobs["jobs"][0]["cv_match_score"] > 0
    assert "CV matches" in jobs["jobs"][0]["fit_reasons"]


def test_saved_job_can_be_unsaved(tmp_path, monkeypatch):
    db_path = str(tmp_path / "unsave_test.db")
    monkeypatch.setenv("DB_PATH", db_path)

    import app.main as main_module
    importlib.reload(main_module)

    from fastapi.testclient import TestClient
    client = TestClient(main_module.app)
    conn = main_module.get_connection(db_path)
    conn.execute(
        "INSERT INTO jobs (source, external_id, url, title, company, description, collected_at, fit_score, fit_reasons, extra_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("wuzzuf", "job-1", "https://example.com/1", "Saved role", "Acme", "A role", "2024-01-01T00:00:00Z", 0.5, "[]", "{}"),
    )
    job_id = conn.execute("SELECT id FROM jobs WHERE external_id = ?", ("job-1",)).fetchone()[0]
    conn.execute(
        "INSERT INTO applications (job_id, status, updated_at) VALUES (?, ?, ?)",
        (job_id, "saved", "2024-01-01T00:00:00Z"),
    )
    conn.commit()
    application_id = conn.execute("SELECT id FROM applications").fetchone()[0]
    conn.close()

    response = client.delete(f"/api/applications/{application_id}")

    assert response.status_code == 200
    assert response.json()["status"] == "deleted"
    assert client.get("/api/applications").json()["applications"] == []


def test_application_confirmation_updates_saved_job_and_analytics(tmp_path, monkeypatch):
    db_path = str(tmp_path / "applied_analytics_test.db")
    monkeypatch.setenv("DB_PATH", db_path)

    import app.main as main_module
    importlib.reload(main_module)

    from fastapi.testclient import TestClient
    client = TestClient(main_module.app)
    conn = main_module.get_connection(db_path)
    conn.execute(
        "INSERT INTO jobs (source, external_id, url, title, company, description, collected_at, fit_score, fit_reasons, extra_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("remotive", "job-1", "https://example.com/1", "Python Developer", "Acme", "APIs", "2024-01-01T00:00:00Z", 0.8, "[]", "{}"),
    )
    job_id = conn.execute("SELECT id FROM jobs WHERE external_id = ?", ("job-1",)).fetchone()[0]
    conn.execute(
        "INSERT INTO applications (job_id, status, updated_at) VALUES (?, ?, ?)",
        (job_id, "saved", "2024-01-01T00:00:00Z"),
    )
    conn.commit()
    conn.close()

    response = client.post(f"/api/applications?job_id={job_id}&status=applied")

    assert response.status_code == 200
    assert response.json()["status"] == "applied"
    applications = client.get("/api/applications?status=applied").json()["applications"]
    assert len(applications) == 1
    assert applications[0]["applied_at"]
    analytics = client.get("/api/applications/analytics").json()
    assert analytics["total"] == 1
    assert analytics["by_company"] == {"Acme": 1}


def test_application_statuses_are_supported_and_deletable(tmp_path, monkeypatch):
    db_path = str(tmp_path / "application_statuses_test.db")
    monkeypatch.setenv("DB_PATH", db_path)

    import app.main as main_module
    importlib.reload(main_module)

    from fastapi.testclient import TestClient
    client = TestClient(main_module.app)
    conn = main_module.get_connection(db_path)
    conn.execute(
        "INSERT INTO jobs (source, external_id, url, title, company, description, collected_at, fit_score, fit_reasons, extra_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("remotive", "job-status", "https://example.com/status", "QA Lead", "Acme", "Testing", "2024-01-01T00:00:00Z", 0.8, "[]", "{}"),
    )
    job_id = conn.execute("SELECT id FROM jobs WHERE external_id = ?", ("job-status",)).fetchone()[0]
    conn.commit()
    conn.close()

    for status in ("interviewing", "rejected", "offer"):
        response = client.post(f"/api/applications?job_id={job_id}&status={status}")
        assert response.status_code == 200
        assert response.json()["status"] == status

    application_id = client.get("/api/applications").json()["applications"][0]["id"]
    assert client.delete(f"/api/applications/{application_id}").status_code == 200


def test_dashboard_includes_applied_jobs_count(tmp_path, monkeypatch):
    db_path = str(tmp_path / "dashboard_test.db")
    monkeypatch.setenv("DB_PATH", db_path)

    import app.main as main_module
    importlib.reload(main_module)

    from fastapi.testclient import TestClient
    client = TestClient(main_module.app)

    conn = main_module.get_connection(db_path)
    conn.execute(
        "INSERT INTO jobs (source, external_id, url, title, company, description, collected_at, fit_score, fit_reasons, extra_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("wuzzuf", "job-1", "https://example.com/1", "QA Analyst", "Acme", "Testing tasks", "2024-01-01T00:00:00Z", 0.9, "[]", "{}"),
    )
    conn.execute(
        "INSERT INTO jobs (source, external_id, url, title, company, description, collected_at, fit_score, fit_reasons, extra_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("wuzzuf", "job-2", "https://example.com/2", "Frontend Dev", "Beta", "Build UI", "2024-01-01T00:00:00Z", 0.7, "[]", "{}"),
    )
    job1_id = conn.execute("SELECT id FROM jobs WHERE url = ?", ("https://example.com/1",)).fetchone()[0]
    job2_id = conn.execute("SELECT id FROM jobs WHERE url = ?", ("https://example.com/2",)).fetchone()[0]
    conn.execute(
        "INSERT INTO applications (job_id, status, applied_at, notes, updated_at) VALUES (?, ?, ?, ?, ?)",
        (job1_id, "applied", "2024-01-02T00:00:00Z", "Applied", "2024-01-02T00:00:00Z"),
    )
    conn.execute(
        "INSERT INTO applications (job_id, status, applied_at, notes, updated_at) VALUES (?, ?, ?, ?, ?)",
        (job2_id, "saved", "2024-01-03T00:00:00Z", "Saved", "2024-01-03T00:00:00Z"),
    )
    conn.commit()
    conn.close()

    response = client.get("/api/dashboard")
    assert response.status_code == 200
    body = response.json()
    assert body["applied_jobs"] == 1
    assert body["saved_jobs"] == 1
    assert body["total_applications"] == 2
    assert body["status_breakdown"]["applied"] == 1
    assert body["status_breakdown"]["saved"] == 1
    assert "application_rate" in body
