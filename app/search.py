"""Search-term cleanup and typo correction for job and location queries."""
from __future__ import annotations

import re
from difflib import get_close_matches

JOB_TERMS = {
    "analyst", "automation", "backend", "business", "developer", "devops",
    "engineer", "frontend", "fullstack", "javascript", "machine", "manager",
    "marketing", "manual", "python", "quality", "qa", "sales", "software",
    "sql", "support", "tester", "testing", "typescript", "web",
}
LOCATION_TERMS = {
    "alexandria", "cairo", "canada", "dubai", "egypt", "giza", "jeddah",
    "london", "new york", "remote", "riyadh", "saudi arabia", "united kingdom",
    "united states", "usa", "washington",
}


def correct_search_text(value: str | None, vocabulary: set[str]) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", value.strip())
    if not cleaned:
        return None

    corrected = cleaned
    for phrase in sorted(vocabulary, key=len, reverse=True):
        if " " in phrase:
            corrected = re.sub(
                rf"\b{re.escape(phrase)}\b", phrase, corrected, flags=re.IGNORECASE
            )
    words = re.findall(r"[A-Za-z][A-Za-z-]*", corrected)
    for word in words:
        if len(word) < 4:
            continue
        match = get_close_matches(word.lower(), vocabulary, n=1, cutoff=0.84)
        if match and match[0] != word.lower():
            corrected = re.sub(
                rf"\b{re.escape(word)}\b", match[0], corrected, count=1, flags=re.IGNORECASE
            )
    return corrected
