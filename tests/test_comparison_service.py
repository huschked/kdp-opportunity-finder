from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from models import Base, Niche, ScoreSnapshot
from services.comparison_service import compare_niches


def _snapshot(
    session: Session,
    niche_id: int,
    *,
    automated: float,
    confidence: float,
    human: float | None = None,
    books: int = 10,
    reviews: int = 100,
    analysis_coverage: float = 1.0,
    warnings: tuple[str, ...] = (),
) -> ScoreSnapshot:
    snapshot = ScoreSnapshot(
        niche_id=niche_id,
        scoring_version="2",
        demand_score=71,
        competition_score=62,
        customer_gap_score=83,
        economics_score=68,
        ai_suitability_score=76,
        expansion_score=59,
        automated_overall_score=automated,
        human_overall_score=human,
        confidence_score=confidence,
        unmet_demand_index=34.5,
        weights_json={
            "demand": 0.25,
            "competition": 0.20,
            "customer_gap": 0.25,
            "economics": 0.15,
            "ai_suitability": 0.10,
            "expansion": 0.05,
        },
        explanation_json={
            "components": {
                "demand": {"missing": []},
                "competition": {"missing": []},
                "customer_gap": {"missing": ["review-linked pain evidence"]},
                "economics": {"missing": []},
                "ai_suitability": {"missing": []},
                "expansion": {"missing": []},
            },
            "confidence": {
                "inputs": {
                    "book_count": books,
                    "review_count": reviews,
                    "reviewed_book_count": books,
                    "field_completeness": 0.9,
                    "analysis_completeness": analysis_coverage,
                },
                "warnings": list(warnings),
            },
        },
    )
    session.add(snapshot)
    session.flush()
    return snapshot


def test_comparison_orders_by_decision_score_without_hiding_human_adjustment() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        adjusted = Niche(name="Adjusted niche", seed_keyword="adjusted")
        automated = Niche(name="Automated niche", seed_keyword="automated")
        session.add_all([adjusted, automated])
        session.flush()
        _snapshot(session, adjusted.id, automated=60, human=92, confidence=78)
        _snapshot(session, automated.id, automated=85, confidence=90)

        result = compare_niches(session, [automated.id, adjusted.id])

    assert [row.niche_name for row in result.rows] == ["Adjusted niche", "Automated niche"]
    assert [row.rank for row in result.rows] == [1, 2]
    assert result.rows[0].automated_score == 60
    assert result.rows[0].human_adjusted_score == 92
    assert result.rows[0].decision_score == 92
    assert result.rows[1].human_adjusted_score is None
    assert set(result.rows[0].components) == {
        "demand", "competition", "customer_gap", "economics", "ai_suitability", "expansion"
    }


def test_comparison_keeps_missing_scores_visible_and_unranked() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        scored = Niche(name="Scored niche", seed_keyword="scored")
        unscored = Niche(name="Unscored niche", seed_keyword="unscored")
        session.add_all([scored, unscored])
        session.flush()
        _snapshot(session, scored.id, automated=72, confidence=75)

        result = compare_niches(session, [unscored.id, scored.id])

    assert result.scored_count == 1
    assert result.rows[-1].niche_name == "Unscored niche"
    assert result.rows[-1].rank is None
    assert result.rows[-1].recommendation == "Not scored"
    assert any("no score snapshot" in warning for warning in result.coverage_warnings)


def test_comparison_flags_sparse_and_materially_unequal_evidence() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        covered = Niche(name="Covered niche", seed_keyword="covered")
        sparse = Niche(name="Sparse niche", seed_keyword="sparse")
        session.add_all([covered, sparse])
        session.flush()
        _snapshot(session, covered.id, automated=70, confidence=88, books=10, reviews=120)
        _snapshot(
            session,
            sparse.id,
            automated=82,
            confidence=42,
            books=2,
            reviews=12,
            analysis_coverage=0.2,
            warnings=("Competitor coverage is 2/10 books.", "Review coverage is 12/100 reviews."),
        )

        result = compare_niches(session, [covered.id, sparse.id])

    warning_text = " ".join(result.coverage_warnings)
    assert "Sparse evidence" in warning_text
    assert "materially unequal" in warning_text
    assert "42.0–88.0" in warning_text
    sparse_row = next(row for row in result.rows if row.niche_name == "Sparse niche")
    assert sparse_row.warning_count == 2
    assert sparse_row.missing_observation_count == 1
    assert sparse_row.recommendation == "Needs more data"
