"""
app/scoring.py

Explainable scoring for a broad junior job search. The platform should rank
junior-friendly roles highly across any domain, not only QA/testing.
"""
from __future__ import annotations

import json
import re

JUNIOR_TERMS = ["junior", "entry level", "entry-level", "fresh grad", "graduate", "0-1", "0-2"]
SENIOR_TERMS = ["senior", "lead", "principal", "10+ years", "8+ years", "manager"]
QA_TERMS = ["qa", "quality assurance", "software tester", "test engineer", "sdet", "manual testing", "automation testing"]
STOPWORDS = {
    "about", "after", "also", "and", "are", "from", "have", "into", "more",
    "that", "the", "their", "this", "with", "you", "your", "will", "work",
}


def score_job(title: str, description: str, career_level: str | None, experience: str | None) -> tuple[float, list[str]]:
    text = f"{title} {description} {career_level or ''} {experience or ''}".lower()
    score = 0.25
    reasons: list[str] = ["generic role is eligible for broad search"]

    if any(t in text for t in QA_TERMS):
        score += 0.15
        reasons.append("mentions QA/testing")
    else:
        reasons.append("no QA/testing keywords found")

    if any(t in text for t in JUNIOR_TERMS):
        score += 0.45
        reasons.append("junior/entry-level signal")

    if any(t in text for t in SENIOR_TERMS):
        score -= 0.45
        reasons.append("senior-level signal (penalized)")

    years = re.search(r"(\d+)\s*\+?\s*years?", text)
    if years and int(years.group(1)) <= 2:
        score += 0.2
        reasons.append(f"experience requirement ({years.group(1)}y) fits junior range")
    elif years and int(years.group(1)) > 3:
        score -= 0.25
        reasons.append(f"experience requirement ({years.group(1)}y) too high for junior")

    if "junior" not in text and "entry level" not in text and "fresh grad" not in text and "graduate" not in text:
        score -= 0.1
        reasons.append("not explicitly junior/entry-level")

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


def score_job_against_cv(job: dict, cv_text: str) -> dict:
    """Blend the baseline score with transparent CV/job keyword overlap."""
    annotated = score_and_annotate(job)
    cv_terms = set(re.findall(r"[a-z][a-z0-9+#.-]{2,}", cv_text.lower())) - STOPWORDS
    job_text = " ".join(
        str(job.get(field) or "")
        for field in ("title", "description", "category", "job_requirements", "experience")
    ).lower()
    job_terms = set(re.findall(r"[a-z][a-z0-9+#.-]{2,}", job_text))
    matched_terms = sorted(cv_terms & job_terms)
    cv_score = min(1.0, len(matched_terms) / 12) if cv_terms else 0.0
    personalized_score = round((annotated["fit_score"] * 0.45) + (cv_score * 0.55), 2)
    reasons = json.loads(annotated["fit_reasons"])
    if matched_terms:
        reasons.append(f"CV matches: {', '.join(matched_terms[:6])}")
    else:
        reasons.append("no strong CV keyword overlap found")
    annotated["fit_score"] = personalized_score
    annotated["cv_match_score"] = round(cv_score, 2)
    annotated["fit_reasons"] = json.dumps(reasons, ensure_ascii=False)
    return annotated
