"""Evidence-aware comparison of the latest niche decision snapshots."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any, Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from analysis.scoring import recommendation_label
from db.query_helpers import latest_score_snapshots
from models import Niche, ScoreSnapshot


COMPONENT_LABELS = {
    "demand": "Demand",
    "competition": "Competitive opportunity",
    "customer_gap": "Customer gap",
    "economics": "Economics",
    "ai_suitability": "AI suitability",
    "expansion": "Expansion",
}


@dataclass(frozen=True, slots=True)
class NicheComparisonRow:
    niche_id: int
    niche_name: str
    status: str
    rank: int | None
    snapshot_id: int | None
    calculated_at: datetime | None
    scoring_version: str | None
    automated_score: float | None
    human_adjusted_score: float | None
    decision_score: float | None
    recommendation: str
    confidence: float | None
    unmet_demand_index: float | None
    components: Mapping[str, float | None]
    warnings: tuple[str, ...]
    missing_observations: tuple[str, ...]
    book_count: int | None
    review_count: int | None
    reviewed_book_count: int | None
    field_completeness: float | None
    analysis_completeness: float | None

    @property
    def warning_count(self) -> int:
        return len(self.warnings)

    @property
    def missing_observation_count(self) -> int:
        return len(self.missing_observations)


@dataclass(frozen=True, slots=True)
class NicheComparison:
    rows: tuple[NicheComparisonRow, ...]
    coverage_warnings: tuple[str, ...]

    @property
    def scored_count(self) -> int:
        return sum(row.snapshot_id is not None for row in self.rows)


def _float_or_none(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value: object) -> int | None:
    numeric = _float_or_none(value)
    return int(numeric) if numeric is not None else None


def _unscored_row(niche: Niche) -> NicheComparisonRow:
    return NicheComparisonRow(
        niche_id=niche.id,
        niche_name=niche.name,
        status=niche.status,
        rank=None,
        snapshot_id=None,
        calculated_at=None,
        scoring_version=None,
        automated_score=None,
        human_adjusted_score=None,
        decision_score=None,
        recommendation="Not scored",
        confidence=None,
        unmet_demand_index=None,
        components={name: None for name in COMPONENT_LABELS},
        warnings=(),
        missing_observations=(),
        book_count=None,
        review_count=None,
        reviewed_book_count=None,
        field_completeness=None,
        analysis_completeness=None,
    )


def _snapshot_row(niche: Niche, snapshot: ScoreSnapshot) -> NicheComparisonRow:
    explanation: Mapping[str, Any] = snapshot.explanation_json or {}
    confidence_payload = explanation.get("confidence", {}) or {}
    confidence_inputs = confidence_payload.get("inputs", {}) or {}
    component_payload = explanation.get("components", {}) or {}

    components = {
        "demand": float(snapshot.demand_score),
        "competition": float(snapshot.competition_score),
        "customer_gap": float(snapshot.customer_gap_score),
        "economics": float(snapshot.economics_score),
        "ai_suitability": float(snapshot.ai_suitability_score),
        "expansion": float(snapshot.expansion_score),
    }
    missing_observations: list[str] = []
    for component_name in COMPONENT_LABELS:
        payload = component_payload.get(component_name, {}) or {}
        for observation in payload.get("missing", []) or []:
            label = f"{COMPONENT_LABELS[component_name]}: {observation}"
            if label not in missing_observations:
                missing_observations.append(label)

    human_score = _float_or_none(snapshot.human_overall_score)
    automated_score = float(snapshot.automated_overall_score)
    decision_score = human_score if human_score is not None else automated_score
    confidence = float(snapshot.confidence_score)
    warnings = tuple(str(item) for item in confidence_payload.get("warnings", []) or [])

    return NicheComparisonRow(
        niche_id=niche.id,
        niche_name=niche.name,
        status=niche.status,
        rank=None,
        snapshot_id=snapshot.id,
        calculated_at=snapshot.calculated_at,
        scoring_version=snapshot.scoring_version,
        automated_score=automated_score,
        human_adjusted_score=human_score,
        decision_score=decision_score,
        recommendation=recommendation_label(decision_score, confidence),
        confidence=confidence,
        unmet_demand_index=_float_or_none(snapshot.unmet_demand_index),
        components=components,
        warnings=warnings,
        missing_observations=tuple(missing_observations),
        book_count=_int_or_none(confidence_inputs.get("book_count")),
        review_count=_int_or_none(confidence_inputs.get("review_count")),
        reviewed_book_count=_int_or_none(confidence_inputs.get("reviewed_book_count")),
        field_completeness=_float_or_none(confidence_inputs.get("field_completeness")),
        analysis_completeness=_float_or_none(confidence_inputs.get("analysis_completeness")),
    )


def _materially_unequal_counts(
    rows: Sequence[NicheComparisonRow],
    field: str,
    *,
    minimum_gap: int,
) -> tuple[int, int] | None:
    values = [getattr(row, field) for row in rows]
    counts = [int(value) for value in values if value is not None]
    if len(counts) < 2:
        return None
    low, high = min(counts), max(counts)
    if low == high:
        return None
    if low == 0 or (high - low >= minimum_gap and high / low >= 2):
        return low, high
    return None


def _coverage_warnings(rows: Sequence[NicheComparisonRow]) -> tuple[str, ...]:
    warnings: list[str] = []
    unscored = [row.niche_name for row in rows if row.snapshot_id is None]
    scored = [row for row in rows if row.snapshot_id is not None]
    if unscored:
        warnings.append(
            "Ranking is incomplete because these selected niches have no score snapshot: "
            + ", ".join(unscored)
            + ". They remain visible but unranked."
        )

    sparse = [row.niche_name for row in scored if row.confidence is not None and row.confidence < 60]
    if sparse:
        warnings.append(
            "Sparse evidence keeps the recommendation at Needs more data for: "
            + ", ".join(sparse)
            + "."
        )

    confidences = [float(row.confidence) for row in scored if row.confidence is not None]
    if len(confidences) >= 2:
        low, high = min(confidences), max(confidences)
        if high - low >= 15:
            warnings.append(
                f"Evidence confidence is materially unequal ({low:.1f}–{high:.1f}, a {high - low:.1f}-point gap). "
                "Interpret score order cautiously."
            )

    book_range = _materially_unequal_counts(scored, "book_count", minimum_gap=3)
    if book_range:
        warnings.append(
            f"Competitor-book coverage is materially unequal ({book_range[0]}–{book_range[1]} books)."
        )
    review_range = _materially_unequal_counts(scored, "review_count", minimum_gap=25)
    if review_range:
        warnings.append(
            f"Review coverage is materially unequal ({review_range[0]}–{review_range[1]} reviews)."
        )

    analysis_values = [
        float(row.analysis_completeness)
        for row in scored
        if row.analysis_completeness is not None
    ]
    if len(analysis_values) >= 2:
        low, high = min(analysis_values), max(analysis_values)
        if high - low >= 0.25:
            warnings.append(
                f"Structured-analysis coverage is materially unequal ({low:.0%}–{high:.0%})."
            )

    versions = {row.scoring_version for row in scored if row.scoring_version}
    if len(versions) > 1:
        warnings.append(
            "Selected snapshots use different scoring versions: "
            + ", ".join(sorted(versions))
            + ". Recalculate them before treating ranks as directly comparable."
        )

    return tuple(warnings)


def compare_niches(session: Session, niche_ids: Sequence[int]) -> NicheComparison:
    """Return latest-snapshot rows with explicit evidence-comparability warnings."""

    ordered_ids = tuple(dict.fromkeys(int(niche_id) for niche_id in niche_ids))
    if not ordered_ids:
        return NicheComparison(rows=(), coverage_warnings=())

    niches = list(session.scalars(select(Niche).where(Niche.id.in_(ordered_ids))))
    niches_by_id = {niche.id: niche for niche in niches}
    missing_ids = [niche_id for niche_id in ordered_ids if niche_id not in niches_by_id]
    if missing_ids:
        raise ValueError(f"Niche not found: {', '.join(str(value) for value in missing_ids)}")

    latest = latest_score_snapshots(session, ordered_ids)
    rows = [
        _snapshot_row(niches_by_id[niche_id], latest[niche_id])
        if niche_id in latest
        else _unscored_row(niches_by_id[niche_id])
        for niche_id in ordered_ids
    ]
    ranked = sorted(
        (row for row in rows if row.decision_score is not None),
        key=lambda row: (
            -float(row.decision_score or 0),
            -float(row.confidence or 0),
            row.niche_name.casefold(),
        ),
    )
    rank_by_id = {row.niche_id: index for index, row in enumerate(ranked, start=1)}
    ranked_rows = [replace(row, rank=rank_by_id.get(row.niche_id)) for row in rows]
    ranked_rows.sort(key=lambda row: (row.rank is None, row.rank or 0, row.niche_name.casefold()))
    return NicheComparison(
        rows=tuple(ranked_rows),
        coverage_warnings=_coverage_warnings(ranked_rows),
    )
