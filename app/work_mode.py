"""Work-mode classification for remote, hybrid, and office job filters."""
from __future__ import annotations

import json
import re

REMOTE_TERMS = ("remote", "work from home", "work-from-home", "telecommute", "distributed", "anywhere")
HYBRID_TERMS = ("hybrid", "flexible workplace", "part remote")
OFFICE_TERMS = ("on-site", "onsite", "in-office", "office based", "office-based", "work from office")


def matches_work_mode(job: dict, requested: str | None) -> bool:
    if not requested or requested == "all":
        return True
    text_parts = [
        str(job.get(field) or "")
        for field in ("title", "description", "job_type", "category", "area")
    ]
    extra = job.get("extra_json")
    if extra:
        try:
            text_parts.append(json.dumps(extra) if isinstance(extra, dict) else str(extra))
        except TypeError:
            pass
    text = re.sub(r"\s+", " ", " ".join(text_parts).lower())
    detected = classify_work_mode(job, text)
    if requested == "remote":
        return detected == "remote"
    if requested == "hybrid":
        return detected == "hybrid"
    if requested == "office":
        return detected == "office"
    return False


def classify_work_mode(job: dict, prepared_text: str | None = None) -> str:
    if prepared_text is None:
        text_parts = [str(job.get(field) or "") for field in ("title", "description", "job_type", "category", "area")]
        extra = job.get("extra_json")
        if extra:
            text_parts.append(json.dumps(extra) if isinstance(extra, dict) else str(extra))
        prepared_text = re.sub(r"\s+", " ", " ".join(text_parts).lower())
    if any(term in prepared_text for term in HYBRID_TERMS):
        return "hybrid"
    if any(term in prepared_text for term in REMOTE_TERMS):
        return "remote"
    return "office"
