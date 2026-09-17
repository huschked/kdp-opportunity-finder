"""Validated, provenance-preserving book and review import workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from analysis.review_cleaning import normalize_review_text, review_text_hash
from collectors import DataFormatError, parse_records
from models import Book, DataSource, ImportBatch, Niche, Review
from models.schemas import BookInput, ImportIssue, ImportResult, ReviewInput


InputT = TypeVar("InputT", bound=BaseModel)


@dataclass(frozen=True, slots=True)
class PreparedRow(Generic[InputT]):
    row_number: int
    value: InputT
    resolved_book_id: int | None = None
    normalized_body: str | None = None
    normalized_hash: str | None = None


@dataclass(slots=True)
class ImportPreview(Generic[InputT]):
    entity_type: str
    filename: str
    file_format: str
    checksum: str
    processed_count: int
    valid_rows: list[PreparedRow[InputT]] = field(default_factory=list)
    issues: list[ImportIssue] = field(default_factory=list)

    @property
    def rejected_count(self) -> int:
        return len({issue.row_number for issue in self.issues})

    @property
    def valid_count(self) -> int:
        return len(self.valid_rows)

    def preview_rows(self) -> list[dict[str, Any]]:
        return [
            {"row": row.row_number, **row.value.model_dump(mode="json")}
            for row in self.valid_rows
        ]


def _checksum(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _validation_issues(row_number: int, exc: ValidationError) -> list[ImportIssue]:
    return [
        ImportIssue(
            row_number=row_number,
            field=".".join(str(part) for part in error["loc"]) or None,
            reason=error["msg"],
            value=error.get("input"),
        )
        for error in exc.errors()
    ]


class ImportService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def prepare_books(
        self,
        *,
        niche_id: int,
        content: bytes,
        file_format: str,
        filename: str,
    ) -> ImportPreview[BookInput]:
        niche = self._require_niche(niche_id)
        preview: ImportPreview[BookInput] = ImportPreview(
            entity_type="book",
            filename=filename,
            file_format=file_format,
            checksum=_checksum(content),
            processed_count=0,
        )
        try:
            records = parse_records(content, file_format, root_key="books")
        except DataFormatError as exc:
            preview.issues.append(ImportIssue(row_number=1, reason=str(exc)))
            return preview

        preview.processed_count = len(records)
        existing = {
            (source, identifier)
            for source, identifier in self.session.execute(
                select(Book.source, Book.source_identifier).where(Book.source_identifier.is_not(None))
            )
        }
        seen: set[tuple[str, str]] = set()
        for record in records:
            if not isinstance(record.values, dict):
                preview.issues.append(
                    ImportIssue(row_number=record.row_number, reason="Row must be an object")
                )
                continue
            try:
                value = BookInput.model_validate(record.values)
            except ValidationError as exc:
                preview.issues.extend(_validation_issues(record.row_number, exc))
                continue
            if value.niche and value.niche.casefold() not in {
                niche.name.casefold(), niche.seed_keyword.casefold()
            }:
                preview.issues.append(ImportIssue(
                    row_number=record.row_number,
                    field="niche",
                    reason=f'Row niche "{value.niche}" does not match selected niche "{niche.name}"',
                    value=value.niche,
                ))
                continue
            if value.source_identifier:
                key = (value.source, value.source_identifier)
                if key in existing or key in seen:
                    preview.issues.append(ImportIssue(
                        row_number=record.row_number,
                        field="source_identifier",
                        reason=f'Duplicate source identifier "{value.source_identifier}" for source "{value.source}"',
                        value=value.source_identifier,
                    ))
                    continue
                seen.add(key)
            preview.valid_rows.append(PreparedRow(record.row_number, value))
        return preview

    def prepare_reviews(
        self,
        *,
        niche_id: int,
        content: bytes,
        file_format: str,
        filename: str,
    ) -> ImportPreview[ReviewInput]:
        self._require_niche(niche_id)
        preview: ImportPreview[ReviewInput] = ImportPreview(
            entity_type="review",
            filename=filename,
            file_format=file_format,
            checksum=_checksum(content),
            processed_count=0,
        )
        try:
            records = parse_records(content, file_format, root_key="reviews")
        except DataFormatError as exc:
            preview.issues.append(ImportIssue(row_number=1, reason=str(exc)))
            return preview

        preview.processed_count = len(records)
        identifier_map: dict[str, list[int]] = {}
        for book_id, identifier in self.session.execute(
            select(Book.id, Book.source_identifier).where(
                Book.niche_id == niche_id, Book.source_identifier.is_not(None)
            )
        ):
            identifier_map.setdefault(identifier, []).append(book_id)

        existing_hashes = {
            (book_id, normalized_hash)
            for book_id, normalized_hash in self.session.execute(
                select(Review.book_id, Review.normalized_hash)
                .join(Book, Book.id == Review.book_id)
                .where(Book.niche_id == niche_id)
            )
        }
        seen_hashes: set[tuple[int, str]] = set()
        for record in records:
            if not isinstance(record.values, dict):
                preview.issues.append(
                    ImportIssue(row_number=record.row_number, reason="Row must be an object")
                )
                continue
            try:
                value = ReviewInput.model_validate(record.values)
            except ValidationError as exc:
                preview.issues.extend(_validation_issues(record.row_number, exc))
                continue
            matches = identifier_map.get(value.book_identifier, [])
            if not matches:
                preview.issues.append(ImportIssue(
                    row_number=record.row_number,
                    field="book_identifier",
                    reason=f'No book in this niche has identifier "{value.book_identifier}"',
                    value=value.book_identifier,
                ))
                continue
            if len(matches) > 1:
                preview.issues.append(ImportIssue(
                    row_number=record.row_number,
                    field="book_identifier",
                    reason=f'Book identifier "{value.book_identifier}" is ambiguous in this niche',
                    value=value.book_identifier,
                ))
                continue
            normalized = normalize_review_text(value.body)
            body_hash = review_text_hash(value.body)
            duplicate_key = (matches[0], body_hash)
            if duplicate_key in existing_hashes or duplicate_key in seen_hashes:
                preview.issues.append(ImportIssue(
                    row_number=record.row_number,
                    field="body",
                    reason="Duplicate review text for this book",
                    value=value.body,
                ))
                continue
            seen_hashes.add(duplicate_key)
            preview.valid_rows.append(PreparedRow(
                row_number=record.row_number,
                value=value,
                resolved_book_id=matches[0],
                normalized_body=normalized,
                normalized_hash=body_hash,
            ))
        return preview

    def import_books(self, *, niche_id: int, preview: ImportPreview[BookInput]) -> ImportResult:
        source, batch = self._start_batch(preview)
        for prepared in preview.valid_rows:
            value = prepared.value
            self.session.add(Book(
                niche_id=niche_id,
                data_source_id=source.id,
                **value.model_dump(),
            ))
        return self._finish_batch(preview, batch)

    def import_reviews(self, *, preview: ImportPreview[ReviewInput]) -> ImportResult:
        source, batch = self._start_batch(preview)
        for prepared in preview.valid_rows:
            value = prepared.value
            payload = value.model_dump(exclude={"book_identifier", "body"})
            self.session.add(Review(
                book_id=prepared.resolved_book_id,
                data_source_id=source.id,
                raw_body=value.body,
                normalized_body=prepared.normalized_body,
                normalized_hash=prepared.normalized_hash,
                **payload,
            ))
        return self._finish_batch(preview, batch)

    def _require_niche(self, niche_id: int) -> Niche:
        niche = self.session.get(Niche, niche_id)
        if niche is None:
            raise ValueError(f"Niche {niche_id} does not exist")
        return niche

    def _start_batch(self, preview: ImportPreview[Any]) -> tuple[DataSource, ImportBatch]:
        source = DataSource(
            source_type=f"{preview.file_format}_import",
            name=preview.filename,
            checksum=preview.checksum,
        )
        self.session.add(source)
        self.session.flush()
        batch = ImportBatch(
            source_id=source.id,
            entity_type=preview.entity_type,
            processed_count=preview.processed_count,
            imported_count=preview.valid_count,
            rejected_count=preview.rejected_count,
            status="pending",
            errors_json=[issue.model_dump(mode="json") for issue in preview.issues] or None,
        )
        self.session.add(batch)
        self.session.flush()
        return source, batch

    def _finish_batch(self, preview: ImportPreview[Any], batch: ImportBatch) -> ImportResult:
        batch.completed_at = datetime.now(timezone.utc)
        if preview.valid_count and preview.rejected_count:
            batch.status = "partial"
        elif preview.valid_count:
            batch.status = "completed"
        else:
            batch.status = "failed"
        self.session.commit()
        return ImportResult(
            batch_id=batch.id,
            processed_count=preview.processed_count,
            imported_count=preview.valid_count,
            rejected_count=preview.rejected_count,
            status=batch.status,
            issues=preview.issues,
        )
