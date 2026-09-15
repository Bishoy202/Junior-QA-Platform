from app.scoring import score_job


def test_junior_qa_scores_high():
    score, reasons = score_job(
        "Junior QA Engineer", "manual testing, 0-1 years experience", "Entry Level", "0-1 years"
    )
    assert score >= 0.7
    assert any("junior" in r for r in reasons)


def test_senior_qa_penalized():
    score, reasons = score_job(
        "Senior QA Lead", "8+ years experience managing a team", "Senior", "8+ years"
    )
    assert score < 0.5
    assert any("senior" in r for r in reasons)


def test_non_qa_scores_low():
    score, reasons = score_job("Marketing Specialist", "no testing involved", "Mid Level", None)
    assert score < 0.3
    assert any("no QA" in r for r in reasons)
