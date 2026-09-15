"""
app/db.py

SQLite schema and connection helper. The jobs table matches
CREATE_TABLE.sql exactly (kept in sync deliberately -- CREATE_TABLE.sql
stays the single source of truth for that table's shape). Two extra
tables (applications, pipeline_runs) support the API surface.
"""
from __future__ import annotations

import sqlite3
import logging
import os
import re
from pathlib import Path
from urllib.parse import unquote, urlparse

LOGGER = logging.getLogger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    company_url TEXT,
    company_logo TEXT,
    description TEXT NOT NULL DEFAULT '',
    salary TEXT,
    experience TEXT,
    vacancies TEXT,
    category TEXT,
    career_level TEXT,
    job_requirements TEXT,
    job_type TEXT,
    area TEXT,
    posted_at TEXT,
    collected_at TEXT NOT NULL,
    fit_score REAL NOT NULL DEFAULT 0,
    fit_reasons TEXT NOT NULL DEFAULT '[]',
    extra_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source);
CREATE INDEX IF NOT EXISTS idx_jobs_fit_score ON jobs(fit_score);

CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL REFERENCES jobs(id),
    status TEXT NOT NULL DEFAULT 'saved',
    applied_at TEXT,
    notes TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    results_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS cv_profiles (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    filename TEXT NOT NULL,
    cv_text TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def resolve_db_path() -> str:
    """Resolve a SQLite file from DATABASE_URL, DB_PATH, or DATA_DIR.

    The current data layer is SQLite-specific. Non-SQLite DATABASE_URL values
    fail early with a clear message instead of silently using local SQLite.
    """
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        parsed = urlparse(database_url)
        if parsed.scheme in {"sqlite", "sqlite3"}:
            path = unquote(parsed.path)
            if re.match(r"^/[A-Za-z]:[\\/]", path):
                path = path[1:]
            if parsed.netloc and parsed.netloc not in {"", "localhost"}:
                path = f"//{parsed.netloc}{path}"
            return str(Path(path).resolve())
        raise RuntimeError(
            "DATABASE_URL is configured for a non-SQLite database, but this "
            "app currently supports SQLite only. Use a Railway Volume with "
            "DATA_DIR/DB_PATH, or add a MySQL-compatible database layer first."
        )
    if os.getenv("DB_PATH"):
        return str(Path(os.environ["DB_PATH"]).expanduser().resolve())
    data_dir = Path(os.getenv("DATA_DIR", str(Path(__file__).resolve().parent.parent / "data"))).expanduser()
    return str((data_dir / "jobs.db").resolve())


def get_connection(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: str) -> None:
    conn = get_connection(db_path)
    try:
        # Search history is intentionally local to the browser now.
        conn.execute("DROP TABLE IF EXISTS search_history")
        conn.executescript(SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()


def log_db_status(db_path: str) -> None:
    conn = get_connection(db_path)
    try:
        jobs = conn.execute("SELECT COUNT(*) AS count FROM jobs").fetchone()["count"]
        LOGGER.info("database target=%s backend=sqlite jobs=%s", db_path, jobs)
    finally:
        conn.close()
