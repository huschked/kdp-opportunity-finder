from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from models import Base, MarketSnapshot, Niche
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

