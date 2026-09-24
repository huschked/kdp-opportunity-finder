from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from db.query_helpers import latest_market_snapshots, latest_score_snapshots
from db.repositories import DashboardRepository
from llm.mock_provider import MockProvider
from models import Base, Book, MarketSnapshot, Niche, Review, ScoreSnapshot
from services.analysis_service import analyze_niche_reviews
from services.import_service import DUPLICATE_LOOKUP_BATCH_SIZE, ImportService
from services.pipeline_service import filter_pipeline, load_pipeline


@contextmanager
def recorded_statements(engine):
    statements: list[str] = []

    def record(_conn, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    try:
        yield statements
    finally:
        event.remove(engine, "before_cursor_execute", record)


def _score(session: Session, niche_id: int, value: float) -> ScoreSnapshot:
    snapshot = ScoreSnapshot(
        niche_id=niche_id,
        scoring_version="2",
        demand_score=value,
        competition_score=value,
        customer_gap_score=value,
        economics_score=value,
        ai_suitability_score=value,
        expansion_score=value,
        automated_overall_score=value,
        confidence_score=80,
        weights_json={},
        explanation_json={"confidence": {"warnings": []}},
    )
    session.add(snapshot)
    session.flush()
    return snapshot


def test_dashboard_totals_use_one_statement() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(Niche(name="One", seed_keyword="one", status="promising"))
        session.commit()
        with recorded_statements(engine) as statements:
            totals = DashboardRepository(session).totals()

    assert totals.niches == totals.promising == 1
    assert len(statements) == 1


def test_latest_snapshot_queries_return_one_row_per_parent_at_history_depth() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        niches = [Niche(name=f"Niche {index}", seed_keyword=f"niche {index}") for index in range(2)]
        session.add_all(niches)
        session.flush()
        niche_ids = [niche.id for niche in niches]
        books = [Book(niche_id=niches[0].id, title=f"Book {index}") for index in range(2)]
        session.add_all(books)
        session.flush()
        book_ids = [book.id for book in books]
        latest_score_ids: dict[int, int] = {}
        latest_market_ids: dict[int, int] = {}
        tied_time = datetime(2026, 9, 23, tzinfo=timezone.utc)
        for niche in niches:
            for value in range(25):
                snapshot = _score(session, niche.id, float(value))
                snapshot.calculated_at = tied_time
                latest_score_ids[niche.id] = snapshot.id
        for book in books:
            for value in range(25):
                snapshot = MarketSnapshot(
                    book_id=book.id,
                    observed_at=tied_time,
                    review_count=value,
                )
                session.add(snapshot)
                session.flush()
                latest_market_ids[book.id] = snapshot.id
        session.commit()

        with recorded_statements(engine) as score_statements:
            score_rows = latest_score_snapshots(session, niche_ids)
        with recorded_statements(engine) as market_statements:
            market_rows = latest_market_snapshots(session, book_ids)

    assert {key: row.id for key, row in score_rows.items()} == latest_score_ids
    assert {key: row.id for key, row in market_rows.items()} == latest_market_ids
    assert len(score_statements) == 1
    assert len(market_statements) == 1


def test_pipeline_filters_reuse_loaded_snapshot_without_queries() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        first = Niche(name="First", seed_keyword="first", status="promising")
        second = Niche(name="Second", seed_keyword="second", status="archived")
        session.add_all([first, second])
        session.flush()
        _score(session, first.id, 75)
        session.commit()

        with recorded_statements(engine) as load_statements:
            snapshot = load_pipeline(session)
        with recorded_statements(engine) as filter_statements:
            filtered = filter_pipeline(snapshot, statuses=["promising"], query="first")

    assert len(load_statements) == 2
    assert filter_statements == []
    assert filtered.visible_count == 1
    assert filtered.total_count == snapshot.total_count == 2
    assert filtered.stage_counts == snapshot.stage_counts


def test_import_duplicate_lookup_is_bounded_by_candidate_batches() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        niche = Niche(name="Import", seed_keyword="import")
        session.add(niche)
        session.flush()
        session.add(Book(niche_id=niche.id, title="Existing", source_identifier="BOOK-000"))
        session.commit()
        niche_id = niche.id
        row_count = DUPLICATE_LOOKUP_BATCH_SIZE + 1
        content = "source,source_identifier,title\n" + "".join(
            f"manual,BOOK-{index:03d},Book {index}\n" for index in range(row_count)
        )

        with recorded_statements(engine) as statements:
            preview = ImportService(session).prepare_books(
                niche_id=niche_id,
                content=content.encode("utf-8"),
                file_format="csv",
                filename="large-books.csv",
            )
        review_content = "book_identifier,body\n" + "".join(
            f"BOOK-000,Review body {index}\n" for index in range(row_count)
        )
        with recorded_statements(engine) as review_statements:
            review_preview = ImportService(session).prepare_reviews(
                niche_id=niche_id,
                content=review_content.encode("utf-8"),
                file_format="csv",
                filename="large-reviews.csv",
            )

    duplicate_queries = [statement for statement in statements if "books.source" in statement]
    review_duplicate_queries = [
        statement for statement in review_statements if "reviews.book_id" in statement
    ]
    assert len(duplicate_queries) == 2
    assert len(review_duplicate_queries) == 2
    assert preview.processed_count == row_count
    assert preview.valid_count == row_count - 1
    assert preview.rejected_count == 1
    assert review_preview.valid_count == row_count


class CountingProvider(MockProvider):
    def __init__(self) -> None:
        self.batch_sizes: list[int] = []
        self.pain_cluster_calls = 0
        self.praise_cluster_calls = 0

    def analyze_reviews(self, reviews):
        self.batch_sizes.append(len(reviews))
        return super().analyze_reviews(reviews)

    def cluster_pain_points(self, candidates):
        self.pain_cluster_calls += 1
        return super().cluster_pain_points(candidates)

    def cluster_praise_features(self, candidates):
        self.praise_cluster_calls += 1
        return super().cluster_praise_features(candidates)


def test_analysis_batches_are_capped_and_cache_invalidates_only_new_content() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        niche = Niche(name="Analysis", seed_keyword="analysis")
        session.add(niche)
        session.flush()
        book = Book(niche_id=niche.id, title="Evidence book")
        session.add(book)
        session.flush()
        for index in range(53):
            body = f"Needs more examples {index}, but the clear diagrams are helpful."
            session.add(Review(
                book_id=book.id,
                raw_body=body,
                normalized_body=body,
                normalized_hash=f"{index:064x}",
            ))
        session.commit()

        first_provider = CountingProvider()
        first = analyze_niche_reviews(
            session,
            niche_id=niche.id,
            provider=first_provider,
            batch_size=500,
        )
        cached_provider = CountingProvider()
        cached = analyze_niche_reviews(session, niche_id=niche.id, provider=cached_provider)

        new_body = "Needs more examples 999, but the clear diagrams are helpful."
        session.add(Review(
            book_id=book.id,
            raw_body=new_body,
            normalized_body=new_body,
            normalized_hash=f"{999:064x}",
        ))
        session.commit()
        changed_provider = CountingProvider()
        changed = analyze_niche_reviews(session, niche_id=niche.id, provider=changed_provider)

    assert first_provider.batch_sizes == [50, 3]
    assert first.analyzed_count == 53
    assert cached.analyzed_count == 0
    assert cached.cached_count == 53
    assert cached_provider.batch_sizes == []
    assert cached_provider.pain_cluster_calls == 0
    assert cached_provider.praise_cluster_calls == 0
    assert changed.analyzed_count == 1
    assert changed.cached_count == 53
    assert changed_provider.batch_sizes == [1]
