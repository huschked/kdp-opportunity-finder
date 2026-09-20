from __future__ import annotations

import csv
from datetime import date, datetime, timezone
import io
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from models import (
    Base,
    Book,
    DataSource,
    MarketSnapshot,
    Niche,
    PainPoint,
    PraiseFeature,
    Review,
    ReviewAnalysis,
    ReviewPainPoint,
    ReviewPraiseFeature,
    ScoreSnapshot,
)
from services.export_service import (
    BOOKS_EXPORT,
    DECISIONS_EXPORT,
    REVIEWS_EXPORT,
    build_export_dataset,
    render_export_csv,
    render_export_json,
)


GENERATED_AT = datetime(2026, 9, 19, 18, 30, tzinfo=timezone.utc)


def _score_snapshot(
    niche_id: int,
    *,
    automated: float,
    confidence: float,
    human: float | None = None,
    calculated_at: datetime | None = None,
) -> ScoreSnapshot:
    return ScoreSnapshot(
        niche_id=niche_id,
        calculated_at=calculated_at or GENERATED_AT,
        scoring_version="decision-2",
        demand_score=71,
        competition_score=62,
        customer_gap_score=84,
        economics_score=58,
        ai_suitability_score=76,
        expansion_score=52,
        automated_overall_score=automated,
        human_overall_score=human,
        confidence_score=confidence,
        unmet_demand_index=None,
        weights_json={
            "demand": 0.25,
            "competition": 0.20,
            "customer_gap": 0.25,
            "economics": 0.15,
            "ai_suitability": 0.10,
            "expansion": 0.05,
        },
        explanation_json={
            "confidence": {
                "warnings": ["Review coverage is sparse."],
                "inputs": {
                    "book_count": 2,
                    "review_count": 7,
                    "reviewed_book_count": 2,
                    "field_completeness": 0.65,
                    "analysis_completeness": 0.4,
                },
            },
            "components": {
                "demand": {"missing": ["best_seller_rank"]},
                "economics": {"missing": ["price"]},
            },
        },
    )


def _csv_rows(dataset) -> list[dict[str, str]]:
    text = render_export_csv(dataset).decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


def test_decision_export_uses_latest_snapshot_and_keeps_uncertainty_separate() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        scored = Niche(name="Traceable niche", seed_keyword="traceable", status="promising")
        unscored = Niche(name="Unscored niche", seed_keyword="unscored")
        session.add_all([scored, unscored])
        session.flush()
        old = _score_snapshot(
            scored.id,
            automated=44,
            confidence=40,
            calculated_at=datetime(2026, 9, 18, tzinfo=timezone.utc),
        )
        latest = _score_snapshot(scored.id, automated=73, human=81, confidence=68)
        session.add_all([old, latest])
        session.flush()

        dataset = build_export_dataset(
            session,
            export_type=DECISIONS_EXPORT,
            generated_at=GENERATED_AT,
        )

        assert dataset.record_count == 2
        assert dataset.filename("csv") == "kdp-niche-decisions-latest-all.csv"
        scored_row = next(row for row in dataset.records if row["niche_id"] == scored.id)
        assert scored_row["score_snapshot_id"] == latest.id
        assert scored_row["automated_score"] == 73
        assert scored_row["human_adjusted_score"] == 81
        assert scored_row["decision_score"] == 81
        assert scored_row["confidence_score"] == 68
        assert scored_row["unmet_demand_index"] is None
        assert scored_row["confidence_warnings"] == ["Review coverage is sparse."]
        assert "Demand: best_seller_rank" in scored_row["missing_observations"]
        assert scored_row["weights"]["customer_gap"] == 0.25

        unscored_row = next(row for row in dataset.records if row["niche_id"] == unscored.id)
        assert unscored_row["score_snapshot_id"] is None
        assert unscored_row["automated_score"] is None
        assert unscored_row["recommendation"] == "Not scored"

        json_payload = json.loads(render_export_json(dataset))
        json_scored = next(
            row for row in json_payload["records"] if row["niche_id"] == scored.id
        )
        assert json_payload["scope"]["snapshot_policy"] == "latest_per_niche"
        assert json_payload["generated_at"] == GENERATED_AT.isoformat()
        assert json_scored["unmet_demand_index"] is None
        assert json_payload["missing_value_policy"].startswith("Missing values remain")

        csv_scored = next(row for row in _csv_rows(dataset) if row["niche_id"] == str(scored.id))
        assert csv_scored["automated_score"] == "73.0"
        assert csv_scored["human_adjusted_score"] == "81.0"
        assert csv_scored["unmet_demand_index"] == ""
        assert json.loads(csv_scored["confidence_warnings"]) == [
            "Review coverage is sparse."
        ]


def test_book_export_filters_one_niche_and_preserves_source_and_market_snapshot_ids() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        source = DataSource(
            source_type="csv",
            name="Owner supplied catalog",
            reference="books.csv",
            checksum="source-checksum",
        )
        target = Niche(name="Book export niche", seed_keyword="books")
        other = Niche(name="Other niche", seed_keyword="other")
        session.add_all([source, target, other])
        session.flush()
        target_book = Book(
            niche_id=target.id,
            data_source_id=source.id,
            source="manual_csv",
            source_identifier="BOOK-001",
            title="A traceable competitor",
            price=None,
            rating=4.2,
            date_collected=GENERATED_AT,
        )
        other_book = Book(
            niche_id=other.id,
            source="manual",
            source_identifier="BOOK-OTHER",
            title="Out of scope",
            date_collected=GENERATED_AT,
        )
        session.add_all([target_book, other_book])
        session.flush()
        market_snapshot = MarketSnapshot(
            book_id=target_book.id,
            observed_at=GENERATED_AT,
            price=None,
            rating=4.2,
            review_count=None,
            best_seller_rank=None,
        )
        session.add(market_snapshot)
        session.flush()

        dataset = build_export_dataset(
            session,
            export_type=BOOKS_EXPORT,
            niche_id=target.id,
            generated_at=GENERATED_AT,
        )

        assert dataset.record_count == 1
        row = dataset.records[0]
        assert row["book_id"] == target_book.id
        assert row["niche_id"] == target.id
        assert row["data_source_id"] == source.id
        assert row["data_source_reference"] == "books.csv"
        assert row["source_identifier"] == "BOOK-001"
        assert row["latest_market_snapshot_id"] == market_snapshot.id
        assert row["price"] is None
        assert row["best_seller_rank"] is None
        assert "Out of scope" not in render_export_json(dataset).decode("utf-8")

        csv_row = _csv_rows(dataset)[0]
        assert csv_row["price"] == ""
        assert csv_row["best_seller_rank"] == ""


def test_review_export_preserves_raw_evidence_analysis_and_derived_link_ids() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        source = DataSource(source_type="json", name="Licensed review file")
        niche = Niche(name="Review export niche", seed_keyword="reviews")
        session.add_all([source, niche])
        session.flush()
        book = Book(
            niche_id=niche.id,
            data_source_id=source.id,
            source="json",
            source_identifier="BOOK-REVIEWS",
            title="Evidence book",
            date_collected=GENERATED_AT,
        )
        session.add(book)
        session.flush()
        review = Review(
            book_id=book.id,
            data_source_id=source.id,
            source="json",
            source_review_identifier="REVIEW-001",
            rating=2,
            title="Needs depth",
            raw_body="I needed worked examples.",
            normalized_body="i needed worked examples.",
            normalized_hash="review-hash",
            review_date=date(2026, 9, 1),
            verified_purchase=None,
            helpful_votes=3,
            date_collected=GENERATED_AT,
        )
        pain = PainPoint(niche_id=niche.id, canonical_name="Missing examples")
        praise = PraiseFeature(niche_id=niche.id, canonical_name="Clear layout")
        session.add_all([review, pain, praise])
        session.flush()
        analysis = ReviewAnalysis(
            review_id=review.id,
            sentiment="negative",
            topics_json=["worked examples"],
            features_json=[],
            desired_outcomes_json=["apply the method"],
            result_json={"schema": "stored"},
            schema_version="1",
            content_hash="analysis-hash",
        )
        pain_link = ReviewPainPoint(
            review_id=review.id,
            pain_point_id=pain.id,
            severity=8,
            solvable=True,
            extraction_text="needed worked examples",
        )
        praise_link = ReviewPraiseFeature(
            review_id=review.id,
            praise_feature_id=praise.id,
            strength=6,
            extraction_text="clear layout",
        )
        session.add_all([analysis, pain_link, praise_link])
        session.flush()

        dataset = build_export_dataset(
            session,
            export_type=REVIEWS_EXPORT,
            niche_id=niche.id,
            generated_at=GENERATED_AT,
        )

        assert dataset.record_count == 1
        row = dataset.records[0]
        assert row["review_id"] == review.id
        assert row["book_id"] == book.id
        assert row["data_source_id"] == source.id
        assert row["source_review_identifier"] == "REVIEW-001"
        assert row["raw_body"] == "I needed worked examples."
        assert row["review_analysis_id"] == analysis.id
        assert row["analysis_content_hash"] == "analysis-hash"
        assert row["verified_purchase"] is None
        assert row["pain_point_links"][0]["review_pain_point_id"] == pain_link.id
        assert row["pain_point_links"][0]["pain_point_id"] == pain.id
        assert row["praise_feature_links"][0]["review_praise_feature_id"] == praise_link.id
        assert row["praise_feature_links"][0]["praise_feature_id"] == praise.id

        json_row = json.loads(render_export_json(dataset))["records"][0]
        assert json_row["verified_purchase"] is None
        assert json_row["analysis_topics"] == ["worked examples"]
        csv_row = _csv_rows(dataset)[0]
        assert csv_row["verified_purchase"] == ""
        assert json.loads(csv_row["pain_point_links"])[0]["pain_point_id"] == pain.id


def test_export_validation_requires_supported_type_and_niche_scope() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        with pytest.raises(ValueError, match="Unsupported export type"):
            build_export_dataset(session, export_type="everything")
        with pytest.raises(ValueError, match="A niche is required"):
            build_export_dataset(session, export_type=BOOKS_EXPORT)
        with pytest.raises(ValueError, match="does not exist"):
            build_export_dataset(session, export_type=REVIEWS_EXPORT, niche_id=999)
