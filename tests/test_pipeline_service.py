from __future__ import annotations

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from models import Base, Niche, NicheStatusTransition, ScoreSnapshot
from services.pipeline_service import (
    STATUS_ORDER,
    change_niche_status,
    load_pipeline,
    status_history,
)


def _snapshot(
    session: Session,
    niche_id: int,
    *,
    automated: float,
    confidence: float,
    human: float | None = None,
    warnings: tuple[str, ...] = (),
) -> ScoreSnapshot:
    snapshot = ScoreSnapshot(
        niche_id=niche_id,
        scoring_version="2",
        demand_score=70,
        competition_score=65,
        customer_gap_score=80,
        economics_score=60,
        ai_suitability_score=75,
        expansion_score=55,
        automated_overall_score=automated,
        human_overall_score=human,
        confidence_score=confidence,
        unmet_demand_index=31,
        weights_json={
            "demand": 0.25,
            "competition": 0.20,
            "customer_gap": 0.25,
            "economics": 0.15,
            "ai_suitability": 0.10,
            "expansion": 0.05,
        },
        explanation_json={"confidence": {"warnings": list(warnings)}},
    )
    session.add(snapshot)
    session.flush()
    return snapshot


def test_status_change_persists_and_appends_auditable_history() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        niche = Niche(name="Workflow niche", seed_keyword="workflow", status="researching")
        session.add(niche)
        session.flush()

        transition = change_niche_status(
            session,
            niche_id=niche.id,
            new_status="validation",
            rationale="The evidence review is ready for a manual validation pass.",
        )
        session.commit()

        assert session.get(Niche, niche.id).status == "validation"
        assert transition.from_status == "researching"
        assert transition.to_status == "validation"
        assert transition.rationale.startswith("The evidence review")
        assert session.scalar(select(func.count(NicheStatusTransition.id))) == 1
        history = status_history(session, niche_id=niche.id)
        assert len(history) == 1
        assert history[0].niche_name == "Workflow niche"


@pytest.mark.parametrize(
    ("new_status", "rationale", "message"),
    [
        ("not-a-status", "Manual decision.", "Invalid pipeline status"),
        ("discovered", "Manual decision.", "already Discovered"),
        ("promising", "   ", "rationale is required"),
    ],
)
def test_status_change_rejects_invalid_noop_or_unexplained_transitions(
    new_status: str,
    rationale: str,
    message: str,
) -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        niche = Niche(name="Guarded niche", seed_keyword="guarded")
        session.add(niche)
        session.flush()

        with pytest.raises(ValueError, match=message):
            change_niche_status(
                session,
                niche_id=niche.id,
                new_status=new_status,
                rationale=rationale,
            )

        assert niche.status == "discovered"
        assert session.scalar(select(func.count(NicheStatusTransition.id))) == 0


def test_pipeline_counts_filters_and_decision_context_stay_separate() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        discovered = Niche(
            name="High score still discovered",
            seed_keyword="high score",
            status="discovered",
        )
        promising = Niche(
            name="Promising workflow niche",
            seed_keyword="workflow opportunity",
            status="promising",
        )
        archived = Niche(
            name="Archived niche",
            seed_keyword="old research",
            status="archived",
        )
        session.add_all([discovered, promising, archived])
        session.flush()
        _snapshot(
            session,
            discovered.id,
            automated=91,
            confidence=45,
            warnings=("Review coverage is sparse.",),
        )
        _snapshot(session, promising.id, automated=72, human=81, confidence=82)

        pipeline = load_pipeline(session)
        filtered = load_pipeline(session, statuses=["promising"], query="workflow")

        assert set(pipeline.stage_counts) == set(STATUS_ORDER)
        assert sum(pipeline.stage_counts.values()) == pipeline.total_count == 3
        assert pipeline.stage_counts["discovered"] == 1
        assert pipeline.stage_counts["promising"] == 1
        assert pipeline.stage_counts["archived"] == 1
        assert pipeline.stage_counts["published"] == 0
        assert filtered.visible_count == 1
        assert filtered.rows[0].niche_name == "Promising workflow niche"
        assert filtered.rows[0].automated_score == 72
        assert filtered.rows[0].human_adjusted_score == 81
        assert filtered.rows[0].decision_score == 81

        discovered_row = next(row for row in pipeline.rows if row.niche_id == discovered.id)
        assert discovered_row.status == "discovered"
        assert discovered_row.recommendation == "Needs more data"
        assert discovered_row.warning_count == 1
        assert session.get(Niche, discovered.id).status == "discovered"

        change_niche_status(
            session,
            niche_id=discovered.id,
            new_status="validation",
            rationale="A human reviewer approved moving it into validation.",
        )
        updated = load_pipeline(session)
        assert updated.stage_counts["discovered"] == 0
        assert updated.stage_counts["validation"] == 1
        assert sum(updated.stage_counts.values()) == updated.total_count
