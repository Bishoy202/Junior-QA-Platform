"""
app/main.py

Real FastAPI app. Serves the static frontend and the API. All endpoints
read from / write to the actual SQLite DB -- nothing here fabricates
rows for display.
"""
from __future__ import annotations

import os
import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .db import init_db, get_connection
from .pipeline import run_pipeline, SOURCES, DISABLED_SOURCES

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "data" / "jobs.db"))
FRONTEND_DIR = BASE_DIR / "frontend"

app = FastAPI(title="Junior QA Job Platform")

# Defensive: if someone opens frontend/index.html directly as a file://
# URL instead of navigating to this server, its fetch() calls arrive from
# a null/file origin and get silently blocked without this. The correct
# way to use the app is still http://127.0.0.1:8000/, but this stops that
# specific mistake from producing a silent, unexplained hang.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db(DB_PATH)


@app.get("/api/health")
def health():
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}


@app.get("/api/sources")
def sources():
    return {
        "enabled": list(SOURCES.keys()),
        "disabled": DISABLED_SOURCES,
    }


@app.get("/api/jobs")
def list_jobs(
    source: str | None = None,
    q: str | None = None,
    location: str | None = None,
    min_fit: float = 0.0,
    limit: int = Query(50, le=200),
    offset: int = 0,
):
    conn = get_connection(DB_PATH)
    try:
        where = ["fit_score >= ?"]
        params: list = [min_fit]
        if source:
            where.append("source = ?")
            params.append(source)
        if q:
            where.append("(title LIKE ? OR company LIKE ? OR description LIKE ? OR category LIKE ?)")
            search = f"%{q.strip()}%"
            params.extend([search] * 4)
        if location:
            where.append("area LIKE ?")
            params.append(f"%{location.strip()}%")
        query = (
            f"SELECT * FROM jobs WHERE {' AND '.join(where)} "
            f"ORDER BY fit_score DESC, posted_at DESC LIMIT ? OFFSET ?"
        )
        params += [limit, offset]
        rows = conn.execute(query, params).fetchall()
        return {"jobs": [dict(r) for r in rows], "count": len(rows)}
    finally:
        conn.close()


@app.get("/api/dashboard")
def dashboard():
    conn = get_connection(DB_PATH)
    try:
        total = conn.execute("SELECT COUNT(*) c FROM jobs").fetchone()["c"]
        by_source = conn.execute(
            "SELECT source, COUNT(*) c FROM jobs GROUP BY source"
        ).fetchall()
        top_fit = conn.execute(
            "SELECT COUNT(*) c FROM jobs WHERE fit_score >= 0.7"
        ).fetchone()["c"]
        last_run = conn.execute(
            "SELECT * FROM pipeline_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return {
            "total_jobs": total,
            "by_source": {r["source"]: r["c"] for r in by_source},
            "high_fit_jobs": top_fit,
            "last_pipeline_run": dict(last_run) if last_run else None,
        }
    finally:
        conn.close()


@app.post("/api/pipeline/run")
def trigger_pipeline():
    result = run_pipeline(DB_PATH)
    return result


@app.get("/api/pipeline/status")
def pipeline_status():
    conn = get_connection(DB_PATH)
    try:
        rows = conn.execute(
            "SELECT * FROM pipeline_runs ORDER BY id DESC LIMIT 5"
        ).fetchall()
        return {"recent_runs": [dict(r) for r in rows]}
    finally:
        conn.close()


@app.get("/api/applications")
def list_applications():
    conn = get_connection(DB_PATH)
    try:
        rows = conn.execute(
            """SELECT applications.*, jobs.title, jobs.company, jobs.url
               FROM applications JOIN jobs ON jobs.id = applications.job_id
               ORDER BY applications.updated_at DESC"""
        ).fetchall()
        return {"applications": [dict(r) for r in rows]}
    finally:
        conn.close()


@app.post("/api/applications")
def create_application(job_id: int, status: str = "saved", notes: str | None = None):
    conn = get_connection(DB_PATH)
    try:
        job = conn.execute("SELECT id FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if not job:
            raise HTTPException(status_code=404, detail="job not found")
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO applications (job_id, status, applied_at, notes, updated_at) VALUES (?, ?, ?, ?, ?)",
            (job_id, status, now if status == "applied" else None, notes, now),
        )
        conn.commit()
        return {"status": "created"}
    finally:
        conn.close()


if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/")
    def index():
        return FileResponse(str(FRONTEND_DIR / "index.html"))
