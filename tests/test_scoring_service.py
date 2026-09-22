from __future__ import annotations

from datetime import date, timedelta
import hashlib

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from models import Base, Book, Niche, PainPoint, Review, ReviewPainPoint, ScoreSnapshot
from services.scoring_service import apply_human_score_override, calculate_niche_score


def test_score_snapshot_preserves_explanations_weights_and_human_override(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{(tmp_path / 'phase4.db').as_posix()}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        niche = Niche(name="Practical test niche", seed_keyword="practical test", status="researching")
        session.add(niche)
        session.flush()
        pain = PainPoint(
            niche_id=niche.id,
            canonical_name="Needs clearer examples",
            system_solvability_score=9,
            confidence=0.9,
        )
        session.add(pain)
        session.flush()
        for index in range(10):
            book = Book(
                niche_id=niche.id,
                source="test",
                source_identifier=f"book-{index}",
                title=f"Book {index}",
                publisher=f"Publisher {index}",
                publication_date=date.today() - timedelta(days=500 + index * 30),
                format="paperback" if index % 2 else "ebook",
                price=16 + index / 2,
                page_count=140 + index,
                rating=4.2,
                review_count=100 + index * 10,
                best_seller_rank=20_000 + index * 1_000,
                date_collected=date.today(),
            )
            session.add(book)
            session.flush()
            body = f"Review {index} needs clearer worked examples."
            review = Review(
                book_id=book.id,
                source="test",
                source_review_identifier=f"review-{index}",
                rating=3,
                raw_body=body,
                normalized_body=body.casefold(),
                normalized_hash=hashlib.sha256(body.encode()).hexdigest(),
                review_date=date.today() - timedelta(days=index),
            )
            session.add(review)
            session.flush()
            session.add(ReviewPainPoint(
                review_id=review.id,
                pain_point_id=pain.id,
                severity=8,
                solvable=True,
                extraction_text="needs clearer worked examples",
            ))

        automated = calculate_niche_score(session, niche.id)
        assert automated.weights_json["customer_gap"] == 0.25
        assert set(automated.explanation_json["components"]) == {
            "demand", "competition", "customer_gap", "economics", "ai_suitability", "expansion"
        }
        assert automated.explanation_json["confidence"]["warnings"]
        automated_value = automated.automated_overall_score

        adjusted = apply_human_score_override(
            session,
            niche_id=niche.id,
            human_score=77.5,
            rationale="A known distribution constraint is not represented in the imported evidence.",
        )
        assert adjusted.human_overall_score == 77.5
        assert adjusted.automated_overall_score == automated_value
        assert adjusted.explanation_json["human_override"]["automated_score_preserved"] == automated_value
        assert session.scalars(select(ScoreSnapshot).where(ScoreSnapshot.niche_id == niche.id)).all().__len__() == 2


def _minimal_snapshot(niche_id: int) -> ScoreSnapshot:
    return ScoreSnapshot(
        niche_id=niche_id,
        scoring_version="2",
        demand_score=60,
        competition_score=60,
        customer_gap_score=60,
        economics_score=60,
        ai_suitability_score=60,
        expansion_score=60,
        automated_overall_score=60,
        human_overall_score=None,
        confidence_score=70,
        unmet_demand_index=None,
        weights_json={
            "demand": 0.25,
            "competition": 0.20,
            "customer_gap": 0.25,
            "economics": 0.15,
            "ai_suitability": 0.10,
            "expansion": 0.05,
        },
        explanation_json={"human_override": None},
    )


@pytest.mark.parametrize(
    ("human_score", "rationale", "message"),
    [
        (-0.1, "Human judgment.", "between 0 and 100"),
        (100.1, "Human judgment.", "between 0 and 100"),
        (72, "   ", "rationale is required"),
    ],
)
def test_human_override_rejects_invalid_values_without_appending_snapshot(
    human_score: float,
    rationale: str,
    message: str,
) -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        niche = Niche(name="Guarded override niche", seed_keyword="guarded override")
        session.add(niche)
        session.flush()
        session.add(_minimal_snapshot(niche.id))
        session.commit()

        with pytest.raises(ValueError, match=message):
            apply_human_score_override(
                session,
                niche_id=niche.id,
                human_score=human_score,
                rationale=rationale,
            )

        assert len(session.scalars(select(ScoreSnapshot)).all()) == 1


def test_human_override_requires_an_automated_snapshot() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        niche = Niche(name="Unscored override niche", seed_keyword="unscored override")
        session.add(niche)
        session.commit()

        with pytest.raises(ValueError, match="Calculate an automated score"):
            apply_human_score_override(
                session,
                niche_id=niche.id,
                human_score=70,
                rationale="Human judgment.",
            )

        assert not session.scalars(select(ScoreSnapshot)).all()
