import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from models import Base, Book, MarketSnapshot, Niche
from models.schemas import BookInput
from services.book_service import BookService


def test_manual_book_edits_append_market_snapshots() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    niche = Niche(name="Manual niche", seed_keyword="manual")
    session.add(niche)
    session.commit()
    service = BookService(session)
    book = service.create(
        niche_id=niche.id,
        value=BookInput(title="First title", source_identifier="MANUAL-1", price=12.99),
    )
    service.update(
        book_id=book.id,
        value=BookInput(title="Updated title", source_identifier="MANUAL-1", price=14.99),
    )
    assert book.title == "Updated title"
    assert session.scalar(select(func.count(MarketSnapshot.id))) == 2


def test_book_creation_rejects_missing_niche_without_persisting_records() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()

    with pytest.raises(ValueError, match="does not exist"):
        BookService(session).create(
            niche_id=999,
            value=BookInput(title="Orphan book", source_identifier="ORPHAN-1"),
        )

    assert session.scalar(select(func.count(Book.id))) == 0
    assert session.scalar(select(func.count(MarketSnapshot.id))) == 0


def test_duplicate_source_identifier_does_not_mutate_book_or_append_snapshot() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    niche = Niche(name="Duplicate guard", seed_keyword="duplicate")
    session.add(niche)
    session.commit()
    service = BookService(session)
    first = service.create(
        niche_id=niche.id,
        value=BookInput(title="First", source_identifier="BOOK-1"),
    )
    second = service.create(
        niche_id=niche.id,
        value=BookInput(title="Second", source_identifier="BOOK-2"),
    )

    with pytest.raises(ValueError, match="already exists"):
        service.update(
            book_id=second.id,
            value=BookInput(title="Changed", source_identifier=first.source_identifier),
        )

    session.refresh(second)
    assert second.title == "Second"
    assert second.source_identifier == "BOOK-2"
    assert session.scalar(select(func.count(MarketSnapshot.id))) == 2
