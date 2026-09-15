"""Standalone Wuzzuf/Egypt adapter diagnostic.

Run from the project root:
    .\.venv\Scripts\python diagnose_egypt.py

This intentionally bypasses FastAPI and the pipeline so the HTTP response,
raw body, and parsed jobs can be inspected independently.
"""
from __future__ import annotations

import json

from app.adapters import wuzzuf_collector


def main() -> None:
    try:
        response = wuzzuf_collector.fetch_response()
        print(f"HTTP status: {response.status_code}")
        print("Response headers:")
        print(dict(response.headers))
        print("Response text:")
        print(response.text)
        response.raise_for_status()
        jobs = [job.as_dict() for job in wuzzuf_collector.parse_feed(response.content)]
        print("Parsed jobs:")
        print(json.dumps(jobs, indent=2, ensure_ascii=False))
    except Exception as exc:
        print(f"Diagnostic failed: {type(exc).__name__}: {exc}")
        print("Parsed jobs: []")


if __name__ == "__main__":
    main()
