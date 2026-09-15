"""
app/pipeline.py

Runs each source adapter independently -- one source failing (network,
missing credentials, bad response) must not stop the others or crash the
run. Dedup relies on the jobs.url UNIQUE constraint: we use
INSERT OR IGNORE, so a repeat run naturally suppresses duplicates without
extra bookkeeping tables.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from .adapters import (
    wuzzuf,
    adzuna,
    jooble,
    usajobs,
    remotive,
    remoteok,
    arbeitnow,
    reed,
    jsearch,
    serpapi,
    jobspipe,
)
from .scoring import score_and_annotate
from .db import get_connection

SOURCES = {
    "wuzzuf": wuzzuf.fetch_jobs,
    "adzuna": adzuna.fetch_jobs,
    "jooble": jooble.fetch_jobs,
    "usajobs": usajobs.fetch_jobs,
    "remotive": remotive.fetch_jobs,
    "remoteok": remoteok.fetch_jobs,
    "arbeitnow": arbeitnow.fetch_jobs,
    "reed": reed.fetch_jobs,
    "jsearch": jsearch.fetch_jobs,
    "serpapi": serpapi.fetch_jobs,
    "jobspipe": jobspipe.fetch_jobs,
}

# Hard-disabled per project policy: no public job-search API exists for
# these, and scraping them violates their terms of service.
DISABLED_SOURCES = ["linkedin", "indeed", "glassdoor"]


def run_pipeline(
    db_path: str,
    query: str | None = None,
    location: str | None = None,
    clear_existing: bool = False,
) -> dict:
    started_at = datetime.now(timezone.utc).isoformat()
    results: dict[str, dict] = {}
    conn = get_connection(db_path)
    total_inserted = 0

    try:
        cleared = _clear_untracked_jobs(conn) if clear_existing else 0
        for name, fetch_fn in SOURCES.items():
            try:
                if query is None and location is None:
                    raw_jobs = fetch_fn()
                else:
                    raw_jobs = fetch_fn(query=query, location=location)
                inserted = _insert_jobs(conn, raw_jobs)
                results[name] = {"status": "ok", "fetched": len(raw_jobs), "inserted": inserted}
                total_inserted += inserted
            except Exception as exc:
                # Isolation: this source's failure does not touch the others.
                results[name] = {"status": "error", "error": str(exc)}

        for name in DISABLED_SOURCES:
            results[name] = {"status": "disabled", "reason": "no legitimate public API / ToS-prohibited"}

        finished_at = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO pipeline_runs (started_at, finished_at, results_json) VALUES (?, ?, ?)",
            (started_at, finished_at, json.dumps(results, ensure_ascii=False)),
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "started_at": started_at,
        "results": results,
        "total_inserted": total_inserted,
        "total_cleared": cleared,
    }


def _clear_untracked_jobs(conn) -> int:
    cursor = conn.execute(
        "DELETE FROM jobs WHERE id NOT IN (SELECT DISTINCT job_id FROM applications)"
    )
    conn.commit()
    return cursor.rowcount


# Matches the NOT NULL DEFAULT values in CREATE_TABLE.sql. Adapters (like
# wuzzuf_collector, which predates this pipeline and wasn't written against
# every column here) don't all populate every key -- fill gaps with the
# same defaults the schema itself declares, rather than passing None into
# a NOT NULL column and having INSERT OR IGNORE silently drop the row.
NOT_NULL_DEFAULTS = {
    "description": "",
    "extra_json": "{}",
    "fit_reasons": "[]",
}


def _insert_jobs(conn, raw_jobs: list[dict]) -> int:
    inserted = 0
    for job in raw_jobs:
        job = score_and_annotate(job)
        cols = [
            "source", "external_id", "url", "title", "company", "company_url",
            "company_logo", "description", "salary", "experience", "vacancies",
            "category", "career_level", "job_requirements", "job_type", "area",
            "posted_at", "collected_at", "fit_score", "fit_reasons", "extra_json",
        ]
        values = []
        for c in cols:
            v = job.get(c)
            if v is None and c in NOT_NULL_DEFAULTS:
                v = NOT_NULL_DEFAULTS[c]
            values.append(v)
        placeholders = ",".join(["?"] * len(cols))
        cur = conn.execute(
            f"INSERT OR IGNORE INTO jobs ({','.join(cols)}) VALUES ({placeholders})",
            values,
        )
        if cur.rowcount > 0:
            inserted += 1
    conn.commit()
    return inserted
