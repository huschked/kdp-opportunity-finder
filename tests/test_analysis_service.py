import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from llm.mock_provider import MockProvider
from llm.base import ProviderContractError
from llm.schemas import ComplaintCategory, PainPointExtraction, ReviewForAnalysis
from models import AnalysisRun, Base, Book, Niche, PainPoint, PraiseFeature, Review, ReviewAnalysis, ReviewPainPoint
from services.analysis_service import analyze_niche_reviews
from services.evidence_service import merge_pain_points, rename_pain_point


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    niche = Niche(name="Evidence niche", seed_keyword="evidence")
    session.add(niche)
    session.flush()
    book = Book(niche_id=niche.id, title="Test book", source_identifier="TEST-1")
    session.add(book)
    session.flush()
    reviews = (
        Review(book_id=book.id, rating=2, title="Too theoretical", raw_body="Too theoretical. Needs more worked examples. The organization is poor.", normalized_body="Too theoretical. Needs more worked examples. The organization is poor.", normalized_hash="a" * 64),
        Review(book_id=book.id, rating=5, title="Useful", raw_body="Clear step-by-step practical examples and helpful diagrams.", normalized_body="Clear step-by-step practical examples and helpful diagrams.", normalized_hash="b" * 64),
        Review(book_id=book.id, rating=1, title="Damaged", raw_body="The package arrived damaged during shipping.", normalized_body="The package arrived damaged during shipping.", normalized_hash="c" * 64),
    )
    session.add_all(reviews)
    session.commit()
    return session, niche


def test_schema_rejects_logistics_as_book_solvable() -> None:
    try:
        PainPointExtraction(
            name="Shipping", description="Damaged delivery", category=ComplaintCategory.SHIPPING,
            severity=8, solvable_in_book=True, solvability_score=9,
            suggested_solution="Change the content", evidence_text="arrived damaged",
        )
    except ValueError as exc:
        assert "book solvability" in str(exc)
    else:
        raise AssertionError("Expected validation to reject a solvable shipping complaint")


def test_mock_provider_is_deterministic_and_evidence_grounded() -> None:
    provider = MockProvider()
    request = [ReviewForAnalysis(review_id=7, rating=2, body="Needs more worked examples.")]
    first = provider.analyze_reviews(request).payload.reviews[0]
    second = provider.analyze_reviews(request).payload.reviews[0]
    assert first == second
    assert first.sentiment.value == "negative"
    assert first.pain_points[0].evidence_text == request[0].body


def test_mock_provider_distinguishes_positive_mixed_and_irrelevant_reviews() -> None:
    reviews = [
        ReviewForAnalysis(review_id=1, rating=5, body="Clear, helpful step-by-step examples."),
        ReviewForAnalysis(review_id=2, rating=4, body="Great overview, but it needs more worked examples."),
        ReviewForAnalysis(review_id=3, rating=1, body="The package arrived damaged during shipping."),
    ]
    results = MockProvider().analyze_reviews(reviews).payload.reviews
    assert [item.sentiment.value for item in results] == ["positive", "mixed", "negative"]
    assert not results[0].pain_points
    assert results[1].pain_points[0].category == ComplaintCategory.BOOK_CONTENT
    assert results[2].pain_points[0].category == ComplaintCategory.SHIPPING


def test_analysis_pipeline_persists_evidence_excludes_logistics_and_reuses_cache() -> None:
    session, niche = make_session()
    first = analyze_niche_reviews(session, niche_id=niche.id, provider=MockProvider(), batch_size=2)
    assert first.review_count == 3
    assert first.analyzed_count == 3
    assert first.excluded_complaint_count == 1
    assert session.scalar(select(func.count(ReviewAnalysis.id))) == 3
    assert session.scalar(select(func.count(ReviewPainPoint.id))) >= 1
    assert session.scalar(select(func.count(PainPoint.id)).where(PainPoint.canonical_name == "Shipping or physical damage")) == 0
    assert session.scalar(select(func.count(PraiseFeature.id))) >= 1
    run = session.get(AnalysisRun, first.run_id)
    assert run.status == "completed"
    assert run.result_json["reviews"]

    second = analyze_niche_reviews(session, niche_id=niche.id, provider=MockProvider())
    assert second.analyzed_count == 0
    assert second.cached_count == 3


def test_human_rename_and_merge_preserve_one_group() -> None:
    session, niche = make_session()
    analyze_niche_reviews(session, niche_id=niche.id, provider=MockProvider())
    points = list(session.scalars(select(PainPoint).where(PainPoint.niche_id == niche.id)))
    assert len(points) >= 2
    renamed = rename_pain_point(session, pain_point_id=points[0].id, canonical_name="Reader needs more application")
    assert renamed.canonical_name == "Reader needs more application"
    target = merge_pain_points(session, source_id=points[1].id, target_id=points[0].id)
    session.commit()
    assert target.canonical_name == "Reader needs more application"
    assert session.get(PainPoint, points[1].id) is None
    analyze_niche_reviews(session, niche_id=niche.id, provider=MockProvider(), force=True)
    assert session.get(PainPoint, target.id).canonical_name == "Reader needs more application"


def test_provider_failure_records_failed_run_without_replacing_current_analysis() -> None:
    session, niche = make_session()
    completed = analyze_niche_reviews(session, niche_id=niche.id, provider=MockProvider())
    before = list(session.scalars(select(ReviewAnalysis).order_by(ReviewAnalysis.review_id)))
    before_results = [(item.analysis_run_id, item.result_json) for item in before]

    class FailingProvider(MockProvider):
        name = "failing"
        model = "test-failure"

        def analyze_reviews(self, reviews):
            raise ProviderContractError("simulated provider failure")

    try:
        analyze_niche_reviews(session, niche_id=niche.id, provider=FailingProvider(), force=True)
    except ProviderContractError:
        pass
    else:
        raise AssertionError("Expected the provider failure to propagate")
    after = list(session.scalars(select(ReviewAnalysis).order_by(ReviewAnalysis.review_id)))
    assert [(item.analysis_run_id, item.result_json) for item in after] == before_results
    assert all(item.analysis_run_id == completed.run_id for item in after)
    failed = session.scalar(select(AnalysisRun).where(AnalysisRun.status == "failed"))
    assert failed and "simulated provider failure" in failed.error_message


def test_analysis_rejects_niche_without_reviews_before_creating_run() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    niche = Niche(name="Empty evidence niche", seed_keyword="empty")
    session.add(niche)
    session.commit()

    with pytest.raises(ValueError, match="no reviews"):
        analyze_niche_reviews(session, niche_id=niche.id, provider=MockProvider())

    assert session.scalar(select(func.count(AnalysisRun.id))) == 0


def test_human_merge_rejects_cross_niche_groups_without_deleting_evidence() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    first_niche = Niche(name="First evidence niche", seed_keyword="first")
    second_niche = Niche(name="Second evidence niche", seed_keyword="second")
    session.add_all([first_niche, second_niche])
    session.flush()
    source = PainPoint(niche_id=first_niche.id, canonical_name="First pain")
    target = PainPoint(niche_id=second_niche.id, canonical_name="Second pain")
    session.add_all([source, target])
    session.commit()

    with pytest.raises(ValueError, match="same niche"):
        merge_pain_points(session, source_id=source.id, target_id=target.id)

    assert session.get(PainPoint, source.id) is not None
    assert session.get(PainPoint, target.id) is not None
