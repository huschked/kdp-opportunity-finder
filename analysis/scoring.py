"""Transparent, configuration-driven score calculations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import yaml


COMPONENTS = (
    "demand",
    "competition",
    "customer_gap",
    "economics",
    "ai_suitability",
    "expansion",
)


def clamp_score(value: float) -> float:
    return round(min(100.0, max(0.0, float(value))), 2)


def load_weights(path: Path) -> dict[str, float]:
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    weights = {name: float(payload["weights"][name]) for name in COMPONENTS}
    if abs(sum(weights.values()) - 1.0) > 1e-9:
        raise ValueError("Scoring weights must total 1.0")
    if any(value < 0 for value in weights.values()):
        raise ValueError("Scoring weights cannot be negative")
    return weights


def calculate_overall_score(scores: Mapping[str, float], weights: Mapping[str, float]) -> float:
    missing = set(COMPONENTS) - scores.keys()
    if missing:
        raise ValueError(f"Missing score components: {', '.join(sorted(missing))}")
    return round(sum(clamp_score(scores[name]) * weights[name] for name in COMPONENTS), 2)


def calculate_unmet_demand_index(
    demand_strength: float,
    gap_strength: float,
    solvability: float,
    competitive_accessibility: float,
) -> float:
    factors = [clamp_score(value) / 100 for value in (
        demand_strength, gap_strength, solvability, competitive_accessibility
    )]
    result = 100.0
    for factor in factors:
        result *= factor
    return round(result, 2)


@dataclass(frozen=True, slots=True)
class ConfidenceInputs:
    book_count: int
    review_count: int
    reviewed_book_count: int
    field_completeness: float
    analysis_completeness: float
    recency_score: float
    evidence_distribution: float = 1.0


@dataclass(frozen=True, slots=True)
class ConfidenceTargets:
    target_books: int = 10
    target_reviews: int = 100
    target_cross_book_coverage: float = 0.70
    target_field_completeness: float = 0.80
    target_analysis_completeness: float = 0.90
    target_recency_score: float = 60.0
    maximum_single_book_share: float = 0.50


def calculate_confidence(
    inputs: ConfidenceInputs,
    targets: ConfidenceTargets = ConfidenceTargets(),
) -> tuple[float, dict[str, float]]:
    book_sample = min(inputs.book_count / targets.target_books, 1.0) * 15
    review_sample = min(inputs.review_count / targets.target_reviews, 1.0) * 20
    cross_book = (
        min(
            (inputs.reviewed_book_count / inputs.book_count) / targets.target_cross_book_coverage,
            1.0,
        ) * 15
        if inputs.book_count
        else 0.0
    )
    field_quality = min(max(inputs.field_completeness, 0), 1) * 15
    analysis_quality = min(max(inputs.analysis_completeness, 0), 1) * 15
    recency = clamp_score(inputs.recency_score) / 100 * 10
    distribution = min(max(inputs.evidence_distribution, 0), 1) * 10
    parts = {
        "book_sample": round(book_sample, 2),
        "review_sample": round(review_sample, 2),
        "cross_book_coverage": round(cross_book, 2),
        "field_completeness": round(field_quality, 2),
        "analysis_completeness": round(analysis_quality, 2),
        "evidence_distribution": round(distribution, 2),
        "recency": round(recency, 2),
    }
    return round(sum(parts.values()), 2), parts


def recommendation_label(score: float, confidence: float) -> str:
    if confidence < 60:
        return "Needs more data"
    if score >= 80 and confidence >= 70:
        return "Strong validation candidate"
    if score >= 70:
        return "Promising"
    if score >= 58:
        return "Worth investigating"
    if score >= 40:
        return "Weak"
    return "Reject"
