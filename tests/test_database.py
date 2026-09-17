from datetime import date

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from db.repositories import DashboardRepository, NicheRepository, ReviewRepository
from models import Base, Book, Niche, Review


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def test_niche_repository_round_trip() -> None:
    session = make_session()
    repository = NicheRepository(session)
    niche = repository.create(name="Test niche", seed_keyword="test keyword")
    session.commit()
    assert repository.get(niche.id).name == "Test niche"
    assert session.scalar(select(func.count(Niche.id))) == 1


def test_dashboard_empty_totals() -> None:
    session = make_session()
    assert DashboardRepository(session).totals().niches == 0


def test_review_repository_combines_book_rating_text_and_date_filters() -> None:
    session = make_session()
    niche = Niche(name="Filtered niche", seed_keyword="filtered")
    session.add(niche)
    session.flush()
    first_book = Book(niche_id=niche.id, title="First", source_identifier="FIRST")
    second_book = Book(niche_id=niche.id, title="Second", source_identifier="SECOND")
    session.add_all((first_book, second_book))
    session.flush()
    session.add_all((
        Review(
            book_id=first_book.id,
            rating=2,
            title="Needs examples",
            raw_body="Needs more worked examples.",
            normalized_body="Needs more worked examples.",
            normalized_hash="a" * 64,
            review_date=date(2026, 8, 1),
        ),
        Review(
            book_id=second_book.id,
            rating=5,
            title="Clear",
            raw_body="Excellent diagrams.",
            normalized_body="Excellent diagrams.",
            normalized_hash="b" * 64,
            review_date=date(2026, 7, 1),
        ),
    ))
    session.commit()
    rows = ReviewRepository(session).search(
        niche_id=niche.id,
        book_id=first_book.id,
        ratings=[2],
        query="worked",
        date_from=date(2026, 8, 1),
        date_to=date(2026, 8, 31),
    )
    assert len(rows) == 1
    assert rows[0]["book"] == "First"
