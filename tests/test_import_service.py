from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from models import Base, Book, DataSource, ImportBatch, Niche, Review
from services.import_service import ImportService


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    niche = Niche(name="Import niche", seed_keyword="import niche")
    session.add(niche)
    session.commit()
    return session, niche


def test_book_csv_import_is_partial_and_preserves_report() -> None:
    session, niche = make_session()
    content = b"""source,source_identifier,title,rating,bsr
manual,BOOK-1,Valid book,4.4,25000
manual,BOOK-2,Invalid rating,8,30000
manual,BOOK-1,Duplicate ID,4.1,40000
"""
    service = ImportService(session)
    preview = service.prepare_books(
        niche_id=niche.id, content=content, file_format="csv", filename="books.csv"
    )
    assert preview.processed_count == 3
    assert preview.valid_count == 1
    assert preview.rejected_count == 2

    result = service.import_books(niche_id=niche.id, preview=preview)
    assert result.status == "partial"
    assert result.imported_count == 1
    assert session.scalar(select(func.count(Book.id))) == 1
    batch = session.scalar(select(ImportBatch))
    source = session.scalar(select(DataSource))
    assert batch.errors_json
    assert source.checksum == preview.checksum


def test_review_import_normalizes_and_rejects_duplicates_and_unknown_books() -> None:
    session, niche = make_session()
    book = Book(
        niche_id=niche.id,
        source="manual",
        source_identifier="BOOK-1",
        title="Known book",
    )
    session.add(book)
    session.commit()
    content = b"""book_identifier,rating,title,body
BOOK-1,3,Needs work,"  Needs   more examples. "
BOOK-1,2,Same thought,Needs more examples.
MISSING,4,Unknown,Clear writing.
"""
    service = ImportService(session)
    preview = service.prepare_reviews(
        niche_id=niche.id, content=content, file_format="csv", filename="reviews.csv"
    )
    assert preview.valid_count == 1
    assert preview.rejected_count == 2
    result = service.import_reviews(preview=preview)
    assert result.status == "partial"
    review = session.scalar(select(Review))
    assert review.raw_body == "  Needs   more examples. "
    assert review.normalized_body == "Needs more examples."
    assert len(review.normalized_hash) == 64


def test_json_object_root_and_row_level_validation() -> None:
    session, niche = make_session()
    content = b'{"books":[{"source_identifier":"JSON-1","title":"Valid"},42]}'
    preview = ImportService(session).prepare_books(
        niche_id=niche.id, content=content, file_format="json", filename="books.json"
    )
    assert preview.processed_count == 2
    assert preview.valid_count == 1
    assert preview.rejected_count == 1
    assert preview.issues[0].reason == "Row must be an object"
    malformed = ImportService(session).prepare_books(
        niche_id=niche.id, content=b"{bad", file_format="json", filename="bad.json"
    )
    assert malformed.valid_count == 0
    assert malformed.issues[0].reason.startswith("Invalid JSON")


def test_book_import_accepts_matching_niche_column_and_rejects_mismatch() -> None:
    session, niche = make_session()
    content = b"""niche,source_identifier,title
Import niche,MATCH-1,Matching row
Another niche,MATCH-2,Mismatched row
"""
    preview = ImportService(session).prepare_books(
        niche_id=niche.id, content=content, file_format="csv", filename="books.csv"
    )
    assert preview.valid_count == 1
    assert preview.rejected_count == 1
    assert preview.issues[0].field == "niche"
