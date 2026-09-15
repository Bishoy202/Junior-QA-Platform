"""
app/main.py

Real FastAPI app. Serves the static frontend and the API. All endpoints
read from / write to the actual SQLite DB -- nothing here fabricates
rows for display.
"""
from __future__ import annotations

import os
import json
import io
import logging
import zipfile
from xml.etree import ElementTree
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi import Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .db import init_db, get_connection, log_db_status, resolve_db_path
from .pipeline import run_pipeline, SOURCES, DISABLED_SOURCES
from .scoring import score_job_against_cv
from .search import JOB_TERMS, LOCATION_TERMS, correct_search_text
from .locations import job_matches_location
from .work_mode import classify_work_mode, matches_work_mode

BASE_DIR = Path(__file__).resolve().parent.parent
LOGGER = logging.getLogger(__name__)
DB_PATH = resolve_db_path()
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
log_db_status(DB_PATH)


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
    work_mode: str | None = Query(None, alias="work_mode"),
    min_fit: float = 0.0,
    limit: int = Query(50, le=200),
    offset: int = 0,
):
    conn = get_connection(DB_PATH)
    try:
        if work_mode not in {None, "all", "remote", "hybrid", "office"}:
            raise HTTPException(status_code=400, detail="invalid work mode")
        q = correct_search_text(q, JOB_TERMS)
        location = correct_search_text(location, LOCATION_TERMS)
        where = ["fit_score >= ?"]
        params: list = [min_fit]
        if source:
            where.append("source = ?")
            params.append(source)
        if q:
            where.append("(title LIKE ? OR company LIKE ? OR description LIKE ? OR category LIKE ?)")
            search = f"%{q.strip()}%"
            params.extend([search] * 4)
        query = (
            f"SELECT * FROM jobs WHERE {' AND '.join(where)} "
            f"ORDER BY fit_score DESC, posted_at DESC"
        )
        rows = conn.execute(query, params).fetchall()
        cv = conn.execute("SELECT cv_text FROM cv_profiles WHERE id = 1").fetchone()
        jobs = [dict(row) for row in rows]
        if location:
            jobs = [job for job in jobs if job_matches_location(job, location)]
        if work_mode:
            jobs = [job for job in jobs if matches_work_mode(job, work_mode)]
        for job in jobs:
            job["work_mode"] = classify_work_mode(job)
        if cv:
            jobs = [score_job_against_cv(job, cv["cv_text"]) for job in jobs]
            jobs.sort(key=lambda job: job["fit_score"], reverse=True)
        jobs = jobs[offset : offset + limit]
        return {"jobs": jobs, "count": len(jobs), "cv_loaded": bool(cv)}
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
        applied_jobs = conn.execute(
            "SELECT COUNT(*) c FROM applications WHERE status = 'applied'"
        ).fetchone()["c"]
        saved_jobs = conn.execute(
            "SELECT COUNT(*) c FROM applications WHERE status = 'saved'"
        ).fetchone()["c"]
        status_breakdown = conn.execute(
            "SELECT status, COUNT(*) c FROM applications GROUP BY status"
        ).fetchall()
        total_applications = applied_jobs + saved_jobs
        application_rate = round((applied_jobs / total) * 100, 1) if total else 0.0
        last_run = conn.execute(
            "SELECT * FROM pipeline_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return {
            "total_jobs": total,
            "by_source": {r["source"]: r["c"] for r in by_source},
            "high_fit_jobs": top_fit,
            "applied_jobs": applied_jobs,
            "saved_jobs": saved_jobs,
            "total_applications": total_applications,
            "status_breakdown": {r["status"]: r["c"] for r in status_breakdown},
            "application_rate": application_rate,
            "last_pipeline_run": dict(last_run) if last_run else None,
        }
    finally:
        conn.close()


@app.post("/api/pipeline/run")
def trigger_pipeline():
    result = run_pipeline(DB_PATH, clear_existing=False)
    return result


def _extract_cv_text(content: bytes, filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix in {".txt", ".md", ".csv"}:
        return content.decode("utf-8", errors="ignore")
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(content))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except ImportError as exc:
            raise HTTPException(500, "PDF support is unavailable; install project requirements") from exc
    if suffix == ".docx":
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                xml = archive.read("word/document.xml")
            root = ElementTree.fromstring(xml)
            return " ".join(node.text or "" for node in root.iter() if node.tag.endswith("}t"))
        except (KeyError, zipfile.BadZipFile, ElementTree.ParseError) as exc:
            raise HTTPException(400, "The DOCX file could not be read") from exc
    raise HTTPException(400, "Upload a .txt, .md, .docx, or .pdf CV")


@app.get("/api/cv")
def cv_status():
    conn = get_connection(DB_PATH)
    try:
        row = conn.execute(
            "SELECT filename, updated_at, length(cv_text) AS text_length FROM cv_profiles WHERE id = 1"
        ).fetchone()
        return {"cv": dict(row) if row else None}
    finally:
        conn.close()


@app.post("/api/cv")
async def upload_cv(file: UploadFile = File(...)):
    content = await file.read()
    if not content:
        raise HTTPException(400, "The CV file is empty")
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(413, "CV files must be 5 MB or smaller")
    text = _extract_cv_text(content, file.filename or "cv.txt").strip()
    if len(text) < 30:
        raise HTTPException(400, "The CV needs more readable text to rate jobs")
    conn = get_connection(DB_PATH)
    try:
        conn.execute(
            "INSERT INTO cv_profiles (id, filename, cv_text, updated_at) VALUES (1, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET filename = excluded.filename, cv_text = excluded.cv_text, updated_at = excluded.updated_at",
            (file.filename or "cv.txt", text, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        return {"filename": file.filename or "cv.txt", "text_length": len(text)}
    finally:
        conn.close()


@app.post("/api/search")
def search_jobs(
    q: str | None = Query(None, max_length=120),
    location: str | None = Query(None, max_length=120),
    source: str | None = Query(None),
    work_mode: str | None = Query(None, alias="work_mode"),
):
    """Fetch fresh results from every configured source for this search."""
    query = correct_search_text(q, JOB_TERMS)
    normalized_location = correct_search_text(location, LOCATION_TERMS)
    if source and source not in SOURCES:
        raise HTTPException(status_code=400, detail="unknown job source")
    if work_mode not in {None, "all", "remote", "hybrid", "office"}:
        raise HTTPException(status_code=400, detail="invalid work mode")
    result = run_pipeline(
        DB_PATH,
        query=query,
        location=normalized_location,
        source=source,
        work_mode=work_mode,
    )
    return {"query": query, "location": normalized_location, **result}


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
def list_applications(status: str | None = None):
    conn = get_connection(DB_PATH)
    try:
        where = ""
        params: list[str] = []
        if status:
            if status not in {"saved", "applied", "interviewing", "rejected", "offer"}:
                raise HTTPException(status_code=400, detail="invalid application status")
            where = "WHERE applications.status = ?"
            params.append(status)
        rows = conn.execute(
            f"""SELECT applications.*, jobs.title, jobs.company, jobs.url, jobs.source
               FROM applications JOIN jobs ON jobs.id = applications.job_id
               {where} ORDER BY applications.updated_at DESC""",
            params,
        ).fetchall()
        return {"applications": [dict(r) for r in rows]}
    finally:
        conn.close()


@app.post("/api/applications")
def create_application(job_id: int, status: str = "saved", notes: str | None = None):
    if status not in {"saved", "applied", "interviewing", "rejected", "offer"}:
        raise HTTPException(status_code=400, detail="invalid application status")
    conn = get_connection(DB_PATH)
    try:
        job = conn.execute("SELECT id FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if not job:
            raise HTTPException(status_code=404, detail="job not found")
        now = datetime.now(timezone.utc).isoformat()
        existing = conn.execute(
            "SELECT id FROM applications WHERE job_id = ? ORDER BY id DESC LIMIT 1",
            (job_id,),
        ).fetchone()
        applied_at = now if status != "saved" else None
        if existing:
            conn.execute(
            "UPDATE applications SET status = ?, applied_at = COALESCE(applied_at, ?), notes = COALESCE(?, notes), updated_at = ? WHERE id = ?",
            (status, applied_at, notes, now, existing["id"]),
            )
        else:
            conn.execute(
                "INSERT INTO applications (job_id, status, applied_at, notes, updated_at) VALUES (?, ?, ?, ?, ?)",
                (job_id, status, applied_at, notes, now),
            )
        conn.commit()
        return {"status": status}
    finally:
        conn.close()


@app.get("/api/applications/analytics")
def application_analytics(
    from_date: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    to_date: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
):
    conn = get_connection(DB_PATH)
    try:
        where = ["applications.status != 'saved'"]
        params: list[str] = []
        if from_date:
            where.append("date(applications.applied_at) >= date(?)")
            params.append(from_date)
        if to_date:
            where.append("date(applications.applied_at) <= date(?)")
            params.append(to_date)
        rows = conn.execute(
            f"""SELECT applications.*, jobs.title, jobs.company, jobs.url, jobs.source
                FROM applications JOIN jobs ON jobs.id = applications.job_id
                WHERE {' AND '.join(where)}
                ORDER BY applications.applied_at DESC""",
            params,
        ).fetchall()
        applications = [dict(row) for row in rows]
        by_date: dict[str, int] = {}
        by_company: dict[str, int] = {}
        for application in applications:
            day = (application.get("applied_at") or "")[:10]
            company = application.get("company") or "Unknown"
            by_date[day] = by_date.get(day, 0) + 1
            by_company[company] = by_company.get(company, 0) + 1
        return {
            "total": len(applications),
            "applications": applications,
            "by_date": dict(sorted(by_date.items())),
            "by_company": dict(sorted(by_company.items(), key=lambda item: (-item[1], item[0]))),
        }
    finally:
        conn.close()


@app.delete("/api/applications/{application_id}")
def delete_saved_application(application_id: int):
    conn = get_connection(DB_PATH)
    try:
        application = conn.execute(
            "SELECT status FROM applications WHERE id = ?", (application_id,)
        ).fetchone()
        if not application:
            raise HTTPException(status_code=404, detail="application not found")
        conn.execute("DELETE FROM applications WHERE id = ?", (application_id,))
        conn.commit()
        return {"status": "deleted"}
    finally:
        conn.close()


if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/")
    def index():
        return FileResponse(str(FRONTEND_DIR / "index.html"))
