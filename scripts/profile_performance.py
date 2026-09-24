"""Profile representative local workflows against disposable synthetic data."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from statistics import median
import sys
from tempfile import TemporaryDirectory
from time import perf_counter
from typing import Callable

from sqlalchemy import event, select
from sqlalchemy.orm import sessionmaker


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db.database import build_engine, initialize_database  # noqa: E402
from db.repositories import BookRepository, DashboardRepository, ReviewRepository  # noqa: E402
from llm.mock_provider import MockProvider  # noqa: E402
from models import Book, MarketSnapshot, Niche, ScoreSnapshot  # noqa: E402
from sample_data.generate import seed_sample_data  # noqa: E402
from services.analysis_service import analyze_niche_reviews  # noqa: E402
from services.comparison_service import compare_niches  # noqa: E402
from services.export_service import (  # noqa: E402
    BOOKS_EXPORT,
    DECISIONS_EXPORT,
    REVIEWS_EXPORT,
    build_export_dataset,
)
from services.import_service import ImportService  # noqa: E402
from services.pipeline_service import filter_pipeline, load_pipeline, status_history  # noqa: E402
from services.scoring_service import calculate_niche_score  # noqa: E402


@dataclass(slots=True)
class SqlCounter:
    statements: int = 0
    selects: int = 0

    def record(self, _conn, _cursor, statement, _parameters, _context, _executemany) -> None:
        self.statements += 1
        if statement.lstrip().upper().startswith(("SELECT", "WITH")):
            self.selects += 1


@contextmanager
def count_sql(engine):
    counter = SqlCounter()
    event.listen(engine, "before_cursor_execute", counter.record)
    try:
        yield counter
    finally:
        event.remove(engine, "before_cursor_execute", counter.record)


def measure(engine, operation: Callable[[], object], repeats: int) -> tuple[float, int, int, object]:
    timings: list[float] = []
    result: object = None
    statements = selects = 0
    for _ in range(repeats):
        started = perf_counter()
        with count_sql(engine) as counter:
            result = operation()
        timings.append((perf_counter() - started) * 1000)
        statements, selects = counter.statements, counter.selects
    return median(timings), statements, selects, result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=5, help="Read-flow repetitions used for median timing")
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be positive")

    with TemporaryDirectory(ignore_cleanup_errors=True) as directory:
        engine = build_engine(f"sqlite:///{Path(directory) / 'performance.db'}")
        session_factory = sessionmaker(bind=engine, expire_on_commit=False)
        initialize_database(engine)
        with session_factory() as session:
            seed_sample_data(session)
            session.commit()
            niche_ids = list(session.scalars(select(Niche.id).order_by(Niche.id)))
        niche_id = niche_ids[0]

        def dashboard() -> str:
            with session_factory() as session:
                repository = DashboardRepository(session)
                totals = repository.totals()
                scores = repository.latest_scores()
                stages = repository.stage_counts()
                analyses = repository.recent_analyses()
                return f"{totals.niches} niches/{len(scores)} scores/{len(stages)} stages/{len(analyses)} runs"

        def niche_competitors() -> int:
            with session_factory() as session:
                return len(BookRepository(session).rows_by_niche(niche_id))

        def niche_reviews() -> int:
            with session_factory() as session:
                books = BookRepository(session).list_by_niche(niche_id)
                repository = ReviewRepository(session)
                repository.analysis_filter_options(niche_id)
                rows = repository.search(niche_id=niche_id)
                return len(books) + len(rows)

        def comparison() -> int:
            with session_factory() as session:
                return len(compare_niches(session, niche_ids).rows)

        def pipeline() -> int:
            with session_factory() as session:
                snapshot = load_pipeline(session)
                status_history(session, limit=50)
                return filter_pipeline(snapshot, statuses=["promising"]).visible_count

        def export(export_type: str):
            def run() -> int:
                with session_factory() as session:
                    dataset = build_export_dataset(
                        session,
                        export_type=export_type,
                        niche_id=niche_id if export_type != DECISIONS_EXPORT else None,
                    )
                    return len(dataset.records)

            return run

        def import_preview() -> str:
            content = b"source,source_identifier,title\nmanual,PROFILE-BOOK,Profile book\n"
            with session_factory() as session:
                preview = ImportService(session).prepare_books(
                    niche_id=niche_id,
                    content=content,
                    file_format="csv",
                    filename="profile.csv",
                )
                return f"{preview.valid_count} valid/{preview.rejected_count} rejected"

        def scoring() -> float:
            with session_factory() as session:
                snapshot = calculate_niche_score(session, niche_id)
                session.rollback()
                return round(float(snapshot.automated_overall_score), 1)

        read_operations = (
            ("dashboard", dashboard),
            ("niche_competitors", niche_competitors),
            ("niche_reviews", niche_reviews),
            ("comparison", comparison),
            ("pipeline", pipeline),
            ("export_books", export(BOOKS_EXPORT)),
            ("export_reviews", export(REVIEWS_EXPORT)),
            ("export_decisions", export(DECISIONS_EXPORT)),
            ("import_preview", import_preview),
            ("scoring", scoring),
        )

        print("flow|median_ms|statements|selects|result")
        for name, operation in read_operations:
            timing, statements, selects, result = measure(engine, operation, args.repeats)
            print(f"{name}|{timing:.3f}|{statements}|{selects}|{result}")

        with session_factory() as session:
            timing, statements, selects, first = measure(
                engine,
                lambda: analyze_niche_reviews(
                    session,
                    niche_id=niche_id,
                    provider=MockProvider(),
                    batch_size=20,
                    force=True,
                ),
                1,
            )
            print(
                f"analysis_refresh|{timing:.3f}|{statements}|{selects}|"
                f"{first.analyzed_count} analyzed/{first.cached_count} cached"
            )
            timing, statements, selects, cached = measure(
                engine,
                lambda: analyze_niche_reviews(
                    session,
                    niche_id=niche_id,
                    provider=MockProvider(),
                ),
                1,
            )
            print(
                f"analysis_cached|{timing:.3f}|{statements}|{selects}|"
                f"{cached.analyzed_count} analyzed/{cached.cached_count} cached"
            )
        engine.dispose()


if __name__ == "__main__":
    main()
