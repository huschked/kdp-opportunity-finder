from pathlib import Path

import pytest

from analysis.scoring import (
    ConfidenceInputs,
    calculate_confidence,
    calculate_overall_score,
    calculate_unmet_demand_index,
    clamp_score,
    load_weights,
    recommendation_label,
)


CONFIG = Path(__file__).resolve().parents[1] / "config" / "scoring.yaml"


def test_default_weights_and_overall_score() -> None:
    weights = load_weights(CONFIG)
    scores = {
        "demand": 80,
        "competition": 70,
        "customer_gap": 90,
        "economics": 60,
        "ai_suitability": 50,
        "expansion": 40,
    }
    assert sum(weights.values()) == pytest.approx(1.0)
    assert calculate_overall_score(scores, weights) == 72.5


def test_score_normalization_and_missing_component() -> None:
    assert clamp_score(-3) == 0
    assert clamp_score(107) == 100
    with pytest.raises(ValueError, match="Missing score components"):
        calculate_overall_score({"demand": 50}, load_weights(CONFIG))


def test_confidence_is_bounded_and_explainable() -> None:
    confidence, parts = calculate_confidence(ConfidenceInputs(
        book_count=10,
        review_count=100,
        reviewed_book_count=10,
        field_completeness=1,
        analysis_completeness=1,
        recency_score=100,
    ))
    assert confidence == 100
    assert sum(parts.values()) == 100


def test_udi_uses_all_four_factors() -> None:
    assert calculate_unmet_demand_index(80, 90, 75, 50) == 27.0


def test_recommendation_is_confidence_gated() -> None:
    assert recommendation_label(90, 30) == "Needs more data"
    assert recommendation_label(83, 80) == "Strong validation candidate"

