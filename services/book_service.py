"""Manual book creation and editing."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import Book, MarketSnapshot, Niche
from models.schemas import BookInput


class BookService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, *, niche_id: int, value: BookInput) -> Book:
        if self.session.get(Niche, niche_id) is None:
            raise ValueError(f"Niche {niche_id} does not exist")
        self._require_unique_identifier(value, exclude_book_id=None)
        book = Book(niche_id=niche_id, **value.model_dump())
        self.session.add(book)
        self.session.flush()
        self._append_snapshot(book)
        self.session.commit()
        return book

    def update(self, *, book_id: int, value: BookInput) -> Book:
        book = self.session.get(Book, book_id)
        if book is None:
            raise ValueError(f"Book {book_id} does not exist")
        self._require_unique_identifier(value, exclude_book_id=book_id)
        for field_name, field_value in value.model_dump().items():
            setattr(book, field_name, field_value)
        self._append_snapshot(book)
        self.session.commit()
        return book

    def _require_unique_identifier(self, value: BookInput, exclude_book_id: int | None) -> None:
        if not value.source_identifier:
            return
        statement = select(Book.id).where(
            Book.source == value.source,
            Book.source_identifier == value.source_identifier,
        )
        if exclude_book_id is not None:
            statement = statement.where(Book.id != exclude_book_id)
        if self.session.scalar(statement) is not None:
            raise ValueError(
                f'Source identifier "{value.source_identifier}" already exists for source "{value.source}"'
            )

    def _append_snapshot(self, book: Book) -> None:
        self.session.add(MarketSnapshot(
            book=book,
            price=book.price,
            rating=book.rating,
            review_count=book.review_count,
            best_seller_rank=book.best_seller_rank,
        ))

