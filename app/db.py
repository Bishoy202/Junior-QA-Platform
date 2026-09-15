"""
app/db.py

SQLite schema and connection helper. The jobs table matches
CREATE_TABLE.sql exactly (kept in sync deliberately -- CREATE_TABLE.sql
stays the single source of truth for that table's shape). Two extra
tables (applications, pipeline_runs) support the API surface.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

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
"""


def get_connection(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: str) -> None:
    conn = get_connection(db_path)
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()
