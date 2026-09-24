"""Reusable bounded queries for latest immutable snapshots."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models import MarketSnapshot, ScoreSnapshot


def latest_score_snapshot_ids(
    niche_ids: Sequence[int] | None = None,
    *,
    name: str = "latest_score_snapshot_ids",
) -> Any:
    """Return one ranked snapshot ID per niche without loading snapshot history."""

    statement = select(
        ScoreSnapshot.id.label("snapshot_id"),
        ScoreSnapshot.niche_id.label("niche_id"),
        func.row_number().over(
            partition_by=ScoreSnapshot.niche_id,
            order_by=(ScoreSnapshot.calculated_at.desc(), ScoreSnapshot.id.desc()),
        ).label("snapshot_rank"),
    )
    if niche_ids is not None:
        statement = statement.where(ScoreSnapshot.niche_id.in_(tuple(dict.fromkeys(niche_ids))))
    return statement.subquery(name)


def latest_score_snapshots(
    session: Session,
    niche_ids: Sequence[int],
) -> dict[int, ScoreSnapshot]:
    """Load only the latest score snapshot for each requested niche."""

    unique_ids = tuple(dict.fromkeys(niche_ids))
    if not unique_ids:
        return {}
    ranked = latest_score_snapshot_ids(unique_ids)
    snapshots = session.scalars(
        select(ScoreSnapshot)
        .join(ranked, ranked.c.snapshot_id == ScoreSnapshot.id)
        .where(ranked.c.snapshot_rank == 1)
    )
    return {snapshot.niche_id: snapshot for snapshot in snapshots}


def latest_market_snapshots(
    session: Session,
    book_ids: Sequence[int],
) -> dict[int, MarketSnapshot]:
    """Load only the latest market snapshot for each requested book."""

    unique_ids = tuple(dict.fromkeys(book_ids))
    if not unique_ids:
        return {}
    ranked = (
        select(
            MarketSnapshot.id.label("snapshot_id"),
            func.row_number().over(
                partition_by=MarketSnapshot.book_id,
                order_by=(MarketSnapshot.observed_at.desc(), MarketSnapshot.id.desc()),
            ).label("snapshot_rank"),
        )
        .where(MarketSnapshot.book_id.in_(unique_ids))
        .subquery("latest_market_snapshot_ids")
    )
    snapshots = session.scalars(
        select(MarketSnapshot)
        .join(ranked, ranked.c.snapshot_id == MarketSnapshot.id)
        .where(ranked.c.snapshot_rank == 1)
    )
    return {snapshot.book_id: snapshot for snapshot in snapshots}
