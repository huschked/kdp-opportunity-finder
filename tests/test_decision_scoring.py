from __future__ import annotations

from analysis.decision import DecisionEvidence, build_decision, score_components
from analysis.scoring import recommendation_label


WEIGHTS = {
    "demand": 0.25,
    "competition": 0.20,
    "customer_gap": 0.25,
    "economics": 0.15,
    "ai_suitability": 0.10,
    "expansion": 0.05,
}


def _evidence(**changes: object) -> DecisionEvidence:
    values: dict[str, object] = {
        "book_count": 10,
        "review_count": 100,
        "analyzed_review_count": 100,
        "reviewed_book_count": 10,
        "analyzed_book_count": 10,
        "market_review_counts": (360, 330, 300, 270, 240, 210, 180, 150, 120, 90),
        "best_seller_ranks": (12000, 15000, 18000, 20000, 24000, 28000, 33000, 39000, 45000, 52000),
        "prices": (15.99, 16.99, 17.99, 18.99, 19.99),
        "ratings": (4.1, 4.2, 4.3, 4.3, 4.4),
        "page_counts": (130, 145, 160, 175, 190),
        "publication_age_days": (400, 600, 800, 1000, 1200, 1400, 1600, 1800, 2000, 2200),
        "recent_review_count": 75,
        "dated_review_count": 90,
        "recent_book_count": 5,
        "dated_book_count": 10,
        "formats": ("paperback", "ebook"),
        "publishers": tuple(f"publisher-{index}" for index in range(10)),
        "solvable_pain_mentions": 30,
        "pain_book_count": 8,
        "pain_severities": (7.0, 8.0, 8.5, 9.0),
        "pain_solvabilities": (8.0, 8.5, 9.0, 9.5),
        "topic_count": 8,
        "outcome_count": 6,
        "pain_point_count": 5,
        "praise_feature_count": 4,
        "field_coverage": {name: 1.0 for name in (
            "price", "rating", "review_count", "best_seller_rank",
            "page_count", "publication_date", "publisher", "format",
        )},
        "collection_recency_score": 95,
        "analyzed_reviews_by_book": (10, 10, 10, 10, 10, 10, 10, 10, 10, 10),
    }
    values.update(changes)
    return DecisionEvidence(**values)


def test_every_component_is_inspectable_and_bounded() -> None:
    components = score_components(_evidence())
    assert set(components) == set(WEIGHTS)
    for component in components.values():
        assert 0 <= component.score <= 100
        assert component.inputs
        assert component.calculation
        assert component.explanation
        assert 0 < component.observed_weight <= 1


def test_customer_gap_uses_only_supplied_solvable_links() -> None:
    no_solvable_evidence = score_components(_evidence(
        solvable_pain_mentions=0,
        pain_book_count=0,
        pain_severities=(),
        pain_solvabilities=(),
        pain_point_count=0,
    ))["customer_gap"]
    assert no_solvable_evidence.score == 0
    assert "solvable pain links" in no_solvable_evidence.missing


def test_sparse_and_concentrated_evidence_reduce_confidence_with_exact_warnings() -> None:
    well_covered = build_decision(_evidence(), WEIGHTS)
    sparse = build_decision(_evidence(
        book_count=3,
        review_count=12,
        analyzed_review_count=5,
        reviewed_book_count=2,
        analyzed_book_count=1,
        analyzed_reviews_by_book=(5,),
        field_coverage={"price": 1 / 3, "best_seller_rank": 0.0},
        collection_recency_score=20,
    ), WEIGHTS)
    concentrated = build_decision(_evidence(analyzed_reviews_by_book=(91, 1, 1, 1, 1, 1, 1, 1, 1, 1)), WEIGHTS)

    assert well_covered.confidence_score > sparse.confidence_score
    assert well_covered.confidence_score > concentrated.confidence_score
    assert any("3/10 books" in warning for warning in sparse.warnings)
    assert any("12/100 reviews" in warning for warning in sparse.warnings)
    assert any("One book supplies" in warning for warning in concentrated.warnings)
    assert sparse.recommendation == "Needs more data"


def test_three_synthetic_market_scenarios_rank_as_intended() -> None:
    attractive_gap = build_decision(_evidence(), WEIGHTS)
    entrenched = build_decision(_evidence(
        market_review_counts=(3200, 2800, 2500, 2200, 1900, 1700, 1500, 1300, 1100, 900),
        ratings=(4.7, 4.7, 4.8, 4.8, 4.9),
        pain_book_count=4,
        solvable_pain_mentions=12,
        pain_severities=(5.0, 6.0),
        pain_solvabilities=(7.0, 7.5),
        topic_count=6,
        outcome_count=4,
    ), WEIGHTS)
    weak_demand = build_decision(_evidence(
        market_review_counts=(8, 12, 15, 18, 20, 22, 25, 28, 30, 32),
        best_seller_ranks=(650000, 700000, 750000, 800000, 850000),
        recent_review_count=10,
        dated_review_count=90,
        solvable_pain_mentions=5,
        pain_book_count=2,
        pain_severities=(4.0, 5.0),
        pain_solvabilities=(6.0, 6.5),
        topic_count=3,
        outcome_count=2,
    ), WEIGHTS)

    assert attractive_gap.automated_overall_score > entrenched.automated_overall_score
    assert attractive_gap.automated_overall_score > weak_demand.automated_overall_score
    assert entrenched.components["demand"].score > weak_demand.components["demand"].score
    assert weak_demand.components["competition"].score > entrenched.components["competition"].score


def test_udi_exposes_all_factors_and_low_confidence_gates_human_score() -> None:
    result = build_decision(_evidence(), WEIGHTS)
    assert set(result.udi_factors) == {
        "demand strength", "gap strength", "solvability", "competitive accessibility"
    }
    assert result.udi_explanation
    assert recommendation_label(95, 59.99) == "Needs more data"
