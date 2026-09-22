from __future__ import annotations

import hashlib

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from db.repositories import ScoreRepository
from llm.mock_provider import MockProvider
from models import Base, Niche, Review
from sample_data.generate import seed_sample_data
from services.report_service import generate_opportunity_report
from services.analysis_service import analyze_niche_reviews


@pytest.fixture()
def sample_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    assert seed_sample_data(session) is True
    return session


def test_report_snapshots_cover_all_three_synthetic_scenarios(sample_session) -> None:
    niches = list(sample_session.scalars(select(Niche).order_by(Niche.id)))
    assert len(niches) == 3
    for niche in niches:
        snapshot = ScoreRepository(sample_session).latest_for_niche(niche.id)
        assert snapshot is not None
        report = generate_opportunity_report(sample_session, niche_id=niche.id)
        snapshot_ref = f"[S{snapshot.id}](#evidence-s{snapshot.id})"

        assert report.markdown.startswith(f"# Opportunity report: {niche.name}")
        assert report.markdown == generate_opportunity_report(sample_session, niche_id=niche.id).markdown
        assert snapshot_ref in report.markdown
        assert "## Decision summary" in report.markdown
        assert "## Evidence health" in report.markdown
        assert "## Score breakdown" in report.markdown
        assert "## Review-linked customer gaps" in report.markdown
        assert "## What readers value" in report.markdown
        assert "## Evidence ledger" in report.markdown
        assert "does not predict sales or make an automatic publish decision" in report.markdown
        assert "sales estimates" in report.markdown
        assert len(report.cited_review_ids) == 6
        for label in (
            "Demand", "Competitive opportunity", "Customer gap",
            "Economics", "AI suitability", "Expansion",
        ):
            matching_rows = [line for line in report.markdown.splitlines() if line.startswith(f"| {label} |")]
            assert len(matching_rows) == 1
            assert snapshot_ref in matching_rows[0]


def test_report_prominently_retains_sparse_evidence_warnings(sample_session) -> None:
    niche = sample_session.scalar(select(Niche).where(Niche.name == "Apartment Balcony Gardening"))
    report = generate_opportunity_report(sample_session, niche_id=niche.id)
    assert report.warnings
    assert "### Warnings" in report.markdown
    assert "Structured analysis covers 0/60 reviews" in report.markdown
    assert "### Missing observations" in report.markdown


def test_report_detects_evidence_added_after_score_snapshot(sample_session) -> None:
    niche = sample_session.scalar(select(Niche).where(Niche.name == "Home Coffee Roasting"))
    book = niche.books[0]
    body = "A newly imported review after the score snapshot."
    sample_session.add(Review(
        book_id=book.id,
        source="test",
        source_review_identifier="later-review",
        rating=3,
        raw_body=body,
        normalized_body=body.casefold(),
        normalized_hash=hashlib.sha256(body.encode()).hexdigest(),
    ))
    sample_session.flush()

    report = generate_opportunity_report(sample_session, niche_id=niche.id)
    assert any("now has 61 reviews" in warning for warning in report.warnings)
    assert "Recalculate before making a decision" in report.markdown


def test_report_detects_analysis_completed_after_score_snapshot(sample_session) -> None:
    niche = sample_session.scalar(select(Niche).where(Niche.name == "Home Coffee Roasting"))
    analyze_niche_reviews(sample_session, niche_id=niche.id, provider=MockProvider(), batch_size=20)

    report = generate_opportunity_report(sample_session, niche_id=niche.id)
    assert any("now has 60 analyzed reviews" in warning for warning in report.warnings)
    assert "snapshot S" in report.markdown


def test_report_requires_a_current_explainable_score_snapshot() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    niche = Niche(name="Unscored niche", seed_keyword="unscored")
    session.add(niche)
    session.flush()
    with pytest.raises(ValueError, match="Calculate a score snapshot"):
        generate_opportunity_report(session, niche_id=niche.id)


def test_report_rejects_snapshot_from_another_niche(sample_session) -> None:
    niches = list(sample_session.scalars(select(Niche).order_by(Niche.id)))
    wrong_snapshot = ScoreRepository(sample_session).latest_for_niche(niches[1].id)
    assert wrong_snapshot is not None

    with pytest.raises(ValueError, match="Calculate a score snapshot"):
        generate_opportunity_report(
            sample_session,
            niche_id=niches[0].id,
            snapshot_id=wrong_snapshot.id,
        )
