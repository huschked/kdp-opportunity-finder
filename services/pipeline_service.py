"""Human-controlled niche pipeline queries and auditable status transitions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from analysis.scoring import recommendation_label
from db.query_helpers import latest_score_snapshots
from models import Niche, NicheStatus, NicheStatusTransition, ScoreSnapshot


STATUS_ORDER = tuple(status.value for status in NicheStatus)
STATUS_LABELS = {status: status.replace("_", " ").title() for status in STATUS_ORDER}
ACTIVE_STATUSES = frozenset(
    {
        NicheStatus.DISCOVERED.value,
        NicheStatus.RESEARCHING.value,
        NicheStatus.PROMISING.value,
        NicheStatus.VALIDATION.value,
        NicheStatus.PRODUCTION.value,
    }
)


@dataclass(frozen=True, slots=True)
class PipelineRow:
    niche_id: int
    niche_name: str
    seed_keyword: str
    status: str
    status_label: str
    niche_updated_at: datetime
    snapshot_id: int | None
    snapshot_calculated_at: datetime | None
    automated_score: float | None
    human_adjusted_score: float | None
    decision_score: float | None
    confidence: float | None
    unmet_demand_index: float | None
    recommendation: str
    warning_count: int


@dataclass(frozen=True, slots=True)
class PipelineSnapshot:
    rows: tuple[PipelineRow, ...]
    stage_counts: Mapping[str, int]
    total_count: int

    @property
    def visible_count(self) -> int:
        return len(self.rows)

    @property
    def active_count(self) -> int:
        return sum(self.stage_counts.get(status, 0) for status in ACTIVE_STATUSES)


@dataclass(frozen=True, slots=True)
class StatusHistoryRow:
    transition_id: int
    niche_id: int
    niche_name: str
    from_status: str
    to_status: str
    rationale: str
    changed_at: datetime


def _pipeline_row(niche: Niche, snapshot: ScoreSnapshot | None) -> PipelineRow:
    if snapshot is None:
        return PipelineRow(
            niche_id=niche.id,
            niche_name=niche.name,
            seed_keyword=niche.seed_keyword,
            status=niche.status,
            status_label=STATUS_LABELS.get(niche.status, niche.status.title()),
            niche_updated_at=niche.updated_at,
            snapshot_id=None,
            snapshot_calculated_at=None,
            automated_score=None,
            human_adjusted_score=None,
            decision_score=None,
            confidence=None,
            unmet_demand_index=None,
            recommendation="Not scored",
            warning_count=0,
        )

    automated_score = float(snapshot.automated_overall_score)
    human_score = (
        float(snapshot.human_overall_score)
        if snapshot.human_overall_score is not None
        else None
    )
    decision_score = human_score if human_score is not None else automated_score
    confidence = float(snapshot.confidence_score)
    explanation = snapshot.explanation_json or {}
    warnings = (explanation.get("confidence", {}) or {}).get("warnings", []) or []
    return PipelineRow(
        niche_id=niche.id,
        niche_name=niche.name,
        seed_keyword=niche.seed_keyword,
        status=niche.status,
        status_label=STATUS_LABELS.get(niche.status, niche.status.title()),
        niche_updated_at=niche.updated_at,
        snapshot_id=snapshot.id,
        snapshot_calculated_at=snapshot.calculated_at,
        automated_score=automated_score,
        human_adjusted_score=human_score,
        decision_score=decision_score,
        confidence=confidence,
        unmet_demand_index=(
            float(snapshot.unmet_demand_index)
            if snapshot.unmet_demand_index is not None
            else None
        ),
        recommendation=recommendation_label(decision_score, confidence),
        warning_count=len(warnings),
    )


def load_pipeline(
    session: Session,
    *,
    statuses: Sequence[str] | None = None,
    query: str = "",
) -> PipelineSnapshot:
    """Load filtered rows plus unfiltered counts for every defined workflow stage."""

    niches = list(session.scalars(select(Niche).order_by(Niche.updated_at.desc(), Niche.name)))
    latest = latest_score_snapshots(session, [niche.id for niche in niches])
    stage_counts = {status: 0 for status in STATUS_ORDER}
    for niche in niches:
        stage_counts[niche.status] = stage_counts.get(niche.status, 0) + 1

    rows = [_pipeline_row(niche, latest.get(niche.id)) for niche in niches]
    order = {status: index for index, status in enumerate(STATUS_ORDER)}
    rows.sort(key=lambda row: (order.get(row.status, len(order)), row.niche_name.casefold()))
    snapshot = PipelineSnapshot(
        rows=tuple(rows),
        stage_counts=stage_counts,
        total_count=len(niches),
    )
    return filter_pipeline(snapshot, statuses=statuses, query=query)


def filter_pipeline(
    snapshot: PipelineSnapshot,
    *,
    statuses: Sequence[str] | None = None,
    query: str = "",
) -> PipelineSnapshot:
    """Filter an already-loaded snapshot without repeating database queries."""

    selected_statuses = tuple(dict.fromkeys(statuses or ()))
    invalid_statuses = [status for status in selected_statuses if status not in STATUS_LABELS]
    if invalid_statuses:
        raise ValueError(f"Invalid pipeline status: {', '.join(invalid_statuses)}")

    rows = list(snapshot.rows)
    if selected_statuses:
        selected = set(selected_statuses)
        rows = [row for row in rows if row.status in selected]
    normalized_query = query.strip().casefold()
    if normalized_query:
        rows = [
            row
            for row in rows
            if normalized_query in row.niche_name.casefold()
            or normalized_query in row.seed_keyword.casefold()
        ]

    return PipelineSnapshot(
        rows=tuple(rows),
        stage_counts=snapshot.stage_counts,
        total_count=snapshot.total_count,
    )


def change_niche_status(
    session: Session,
    *,
    niche_id: int,
    new_status: str,
    rationale: str,
) -> NicheStatusTransition:
    """Persist one explicit manual transition without changing any decision score."""

    niche = session.get(Niche, niche_id)
    if niche is None:
        raise ValueError("Niche not found")
    try:
        target_status = NicheStatus(new_status).value
    except ValueError as exc:
        raise ValueError(f"Invalid pipeline status: {new_status}") from exc
    normalized_rationale = rationale.strip()
    if not normalized_rationale:
        raise ValueError("A rationale is required for a status change")
    if niche.status == target_status:
        raise ValueError(f"{niche.name} is already {STATUS_LABELS[target_status]}")

    transition = NicheStatusTransition(
        niche_id=niche.id,
        from_status=niche.status,
        to_status=target_status,
        rationale=normalized_rationale,
    )
    niche.status = target_status
    session.add(transition)
    session.flush()
    return transition


def status_history(
    session: Session,
    *,
    niche_id: int | None = None,
    limit: int = 50,
) -> tuple[StatusHistoryRow, ...]:
    if limit <= 0:
        raise ValueError("History limit must be positive")
    statement = (
        select(NicheStatusTransition, Niche.name)
        .join(Niche, Niche.id == NicheStatusTransition.niche_id)
        .order_by(NicheStatusTransition.changed_at.desc(), NicheStatusTransition.id.desc())
        .limit(limit)
    )
    if niche_id is not None:
        statement = statement.where(NicheStatusTransition.niche_id == niche_id)
    return tuple(
        StatusHistoryRow(
            transition_id=transition.id,
            niche_id=transition.niche_id,
            niche_name=niche_name,
            from_status=transition.from_status,
            to_status=transition.to_status,
            rationale=transition.rationale,
            changed_at=transition.changed_at,
        )
        for transition, niche_name in session.execute(statement)
    )
