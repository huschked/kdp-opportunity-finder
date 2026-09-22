from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from db.repositories import ConceptRepository
from llm.mock_provider import MockProvider
from models import Base, BookConcept, Niche
from sample_data.generate import seed_sample_data
from services.analysis_service import analyze_niche_reviews
from services.concept_service import (
    ASSUMPTION,
    EVIDENCE_BACKED,
    RISK_REVIEW,
    generate_book_specification,
    render_book_specification,
    validate_book_specification,
)
from services.scoring_service import calculate_niche_score


@pytest.fixture()
def sample_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    assert seed_sample_data(session) is True
    return session


def _design_choices(payload):
    return [
        payload["working_title"], payload["target_reader"], payload["core_problem"],
        payload["desired_outcome"], payload["positioning"], *payload["content_plan"],
        *payload["feature_plan"], *payload["format_plan"],
    ]


def test_sparse_specification_labels_assumptions_and_preserves_evidence(sample_session) -> None:
    niches = list(sample_session.scalars(select(Niche).order_by(Niche.id)))
    for niche in niches:
        concept = generate_book_specification(sample_session, niche_id=niche.id)
        payload = concept.concept_json
        evidence_refs = {row["ref"] for row in concept.evidence_json}
        choices = _design_choices(payload)

        assert payload["working_title"]["status"] == ASSUMPTION
        assert payload["target_reader"]["status"] == ASSUMPTION
        assert payload["desired_outcome"]["status"] == ASSUMPTION
        assert payload["core_problem"]["status"] == EVIDENCE_BACKED
        assert payload["positioning"]["status"] == EVIDENCE_BACKED
        assert payload["risk_review"]
        assert all(item["status"] == RISK_REVIEW for item in payload["risk_review"])
        for choice in choices:
            if choice["status"] == EVIDENCE_BACKED:
                assert choice["evidence_refs"]
            if not choice["evidence_refs"]:
                assert choice["status"] == ASSUMPTION
            assert set(choice["evidence_refs"]) <= evidence_refs

        artifact = render_book_specification(concept)
        assert artifact.markdown.startswith(f"# Book specification: {niche.name}")
        assert "**Evidence-backed:**" in artifact.markdown
        assert "**Assumption to validate:**" in artifact.markdown
        assert "**Risk review required:**" in artifact.markdown
        assert "## Evidence limitations and validation" in artifact.markdown
        assert "Planning draft only" in artifact.markdown


def test_analyzed_reviews_ground_reader_outcome_and_topic_choices(sample_session) -> None:
    niche = sample_session.scalar(select(Niche).where(Niche.name == "Home Coffee Roasting"))
    analyze_niche_reviews(sample_session, niche_id=niche.id, provider=MockProvider(), batch_size=20)
    calculate_niche_score(sample_session, niche.id)
    concept = generate_book_specification(sample_session, niche_id=niche.id)
    payload = concept.concept_json

    assert payload["target_reader"]["status"] == EVIDENCE_BACKED
    assert payload["desired_outcome"]["status"] == EVIDENCE_BACKED
    assert any(item["status"] == EVIDENCE_BACKED for item in payload["content_plan"])
    assert all(ref.startswith("R") for ref in payload["target_reader"]["evidence_refs"])
    assert all(ref.startswith("R") for ref in payload["desired_outcome"]["evidence_refs"])


def test_regulated_topic_requires_explicit_expert_review(sample_session) -> None:
    niche = sample_session.scalar(select(Niche).where(Niche.name == "Antique Button Collecting"))
    niche.name = "Medical Antique Button Collecting"
    niche.seed_keyword = "medical collecting guide"
    sample_session.flush()
    calculate_niche_score(sample_session, niche.id)
    concept = generate_book_specification(sample_session, niche_id=niche.id)
    risk_text = " ".join(item["recommendation"] for item in concept.concept_json["risk_review"])

    assert "qualified expert review" in risk_text
    assert "medical" in risk_text
    assert all(item["status"] == RISK_REVIEW for item in concept.concept_json["risk_review"])


def test_specification_history_is_append_only(sample_session) -> None:
    niche = sample_session.scalar(select(Niche).where(Niche.name == "Apartment Balcony Gardening"))
    first = generate_book_specification(sample_session, niche_id=niche.id)
    second = generate_book_specification(sample_session, niche_id=niche.id)
    history = ConceptRepository(sample_session).history_for_niche(niche.id)

    assert first.id != second.id
    assert [item.id for item in history] == [second.id, first.id]
    assert len(sample_session.scalars(select(BookConcept).where(BookConcept.niche_id == niche.id)).all()) == 2


def test_validator_rejects_uncited_claims_disguised_as_evidence() -> None:
    payload = {
        "working_title": {"recommendation": "Title", "rationale": "", "status": EVIDENCE_BACKED, "evidence_refs": []},
        "target_reader": {"recommendation": "Reader", "rationale": "", "status": ASSUMPTION, "evidence_refs": []},
        "core_problem": {"recommendation": "Problem", "rationale": "", "status": ASSUMPTION, "evidence_refs": []},
        "desired_outcome": {"recommendation": "Outcome", "rationale": "", "status": ASSUMPTION, "evidence_refs": []},
        "positioning": {"recommendation": "Position", "rationale": "", "status": ASSUMPTION, "evidence_refs": []},
        "content_plan": [], "feature_plan": [], "format_plan": [],
        "risk_review": [{"recommendation": "Review", "rationale": "", "status": RISK_REVIEW, "evidence_refs": ["S1"]}],
    }
    with pytest.raises(ValueError, match="must cite evidence"):
        validate_book_specification(payload, [{"ref": "S1"}])


def test_specification_requires_a_score_snapshot(sample_session) -> None:
    niche = Niche(name="Unscored specification niche", seed_keyword="unscored spec")
    sample_session.add(niche)
    sample_session.commit()

    with pytest.raises(ValueError, match="Calculate a score snapshot"):
        generate_book_specification(sample_session, niche_id=niche.id)

    assert not sample_session.scalars(
        select(BookConcept).where(BookConcept.niche_id == niche.id)
    ).all()
