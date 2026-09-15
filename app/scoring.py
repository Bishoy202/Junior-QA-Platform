"""
app/scoring.py

Deliberately simple, explainable scoring -- keyword rules, not a black
box -- because the whole point is a junior QA candidate being able to see
*why* a job scored the way it did (fit_reasons).
"""
from __future__ import annotations

import json
import re

JUNIOR_TERMS = ["junior", "entry level", "entry-level", "fresh grad", "graduate", "0-1", "0-2"]
SENIOR_TERMS = ["senior", "lead", "principal", "10+ years", "8+ years", "manager"]
QA_TERMS = ["qa", "quality assurance", "software tester", "test engineer", "sdet", "manual testing", "automation testing"]


def score_job(title: str, description: str, career_level: str | None, experience: str | None) -> tuple[float, list[str]]:
    text = f"{title} {description} {career_level or ''} {experience or ''}".lower()
    score = 0.0
    reasons: list[str] = []

    if any(t in text for t in QA_TERMS):
        score += 0.5
        reasons.append("mentions QA/testing")
    else:
        reasons.append("no QA/testing keywords found")

    if any(t in text for t in JUNIOR_TERMS):
        score += 0.4
        reasons.append("junior/entry-level signal")

    if any(t in text for t in SENIOR_TERMS):
        score -= 0.4
        reasons.append("senior-level signal (penalized)")

    years = re.search(r"(\d+)\s*\+?\s*years?", text)
    if years and int(years.group(1)) <= 2:
        score += 0.1
        reasons.append(f"experience requirement ({years.group(1)}y) fits junior range")
    elif years and int(years.group(1)) > 3:
        score -= 0.2
        reasons.append(f"experience requirement ({years.group(1)}y) too high for junior")

    score = max(0.0, min(1.0, score))
    return round(score, 2), reasons


def score_and_annotate(job: dict) -> dict:
    fit_score, reasons = score_job(
        job.get("title", ""), job.get("description", ""),
        job.get("career_level"), job.get("experience"),
    )
    job = dict(job)
    job["fit_score"] = fit_score
    job["fit_reasons"] = json.dumps(reasons, ensure_ascii=False)
    return job
