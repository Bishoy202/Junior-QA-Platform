"""Consistent tolerant location matching for source and stored-job filters."""
from __future__ import annotations

import re
import unicodedata

ALIASES = {
    "cairo": {"cairo", "new cairo", "cairo, egypt", "cairo egypt"},
    "giza": {"giza", "giza, egypt", "6th of october", "6 october"},
    "alexandria": {"alexandria", "alexandria, egypt"},
}


def normalize_location(value: str | None) -> str:
    if not value:
        return ""
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def location_matches(job_location: str | None, requested_location: str | None) -> bool:
    requested = normalize_location(requested_location)
    if not requested:
        return True
    actual = normalize_location(job_location)
    if not actual:
        return False
    if requested in actual:
        return True
    for alias in ALIASES.get(requested, set()):
        if normalize_location(alias) in actual:
            return True
    requested_words = set(requested.split())
    actual_words = set(actual.split())
    return bool(requested_words) and requested_words.issubset(actual_words)
