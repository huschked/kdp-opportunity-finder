"""Interactive Phase 2 research panels."""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

import pandas as pd
from pydantic import ValidationError
import streamlit as st

from collectors.templates import (
    BOOKS_CSV_TEMPLATE,
    BOOKS_JSON_TEMPLATE,
    REVIEWS_CSV_TEMPLATE,
    REVIEWS_JSON_TEMPLATE,
)
from config.logging import log_event
from db.database import session_scope
from db.repositories import BookRepository, NicheRepository
from models import Book, Niche
from models.schemas import BookInput
from services.book_service import BookService
from services.import_service import ImportPreview, ImportService
from services.niche_service import NicheNameConflict, NicheService
from ui.errors import render_operation_error


def load_niches() -> list[Niche]:
    with session_scope() as session:
        return NicheRepository(session).list_all()


def select_niche(niches: list[Niche], *, key: str) -> Niche | None:
    if not niches:
        st.info("Create a niche before adding market evidence.")
        return None
    by_id = {niche.id: niche for niche in niches}
    selected_id = st.selectbox(
        "Niche",
        options=list(by_id),
        format_func=lambda niche_id: by_id[niche_id].name,
        key=key,
        persist_state="session",
    )
    return by_id[selected_id]


def render_create_niche() -> None:
    st.subheader("Create a niche hypothesis")
    st.caption("A niche starts as a hypothesis. Add observed books and reviews before treating it as evidence.")
    with st.form("create_niche", clear_on_submit=True):
        name = st.text_input("Niche name", max_chars=250)
        seed = st.text_input("Seed keyword", max_chars=250)
        description = st.text_area("Description")
        notes = st.text_area("Notes")
        submitted = st.form_submit_button(
            "Create niche", type="primary", icon=":material/add:"
        )
    if submitted:
        try:
            with session_scope() as session:
                niche = NicheService(session).create_niche(
                    name=name, seed_keyword=seed, description=description, notes=notes
                )
            st.success(f"Created {niche.name}. It is marked Discovered.")
        except (ValueError, NicheNameConflict) as exc:
            render_operation_error(
                exc,
                operation="niche.create",
                summary="The niche was not created.",
                recovery="Use a non-empty, unique niche name and seed keyword, then try again.",
                context={"entity": "niche", "action": "create"},
                expected=True,
            )


def _number_default(value: int | float | None) -> int | float | None:
    return value


def _book_form_values(book: Book | None, prefix: str) -> tuple[bool, dict[str, Any]]:
    with st.form(f"{prefix}_book_form"):
        title = st.text_input("Title", value=book.title if book else "", max_chars=500)
        subtitle = st.text_input("Subtitle", value=book.subtitle or "" if book else "", max_chars=500)
        first, second, third = st.columns(3)
        with first:
            author = st.text_input("Author", value=book.author or "" if book else "", max_chars=250)
            publisher = st.text_input("Publisher", value=book.publisher or "" if book else "", max_chars=250)
            publication_date = st.date_input(
                "Publication date", value=book.publication_date if book else None, format="YYYY-MM-DD"
            )
        with second:
            book_format = st.selectbox(
                "Format",
                ("Not specified", "Paperback", "Hardcover", "eBook", "Spiral-bound", "Other"),
                index=(
                    ("Not specified", "Paperback", "Hardcover", "eBook", "Spiral-bound", "Other").index(book.format)
                    if book and book.format in ("Not specified", "Paperback", "Hardcover", "eBook", "Spiral-bound", "Other")
                    else 0
                ),
            )
            price = st.number_input("Price", min_value=0.0, value=_number_default(book.price if book else None), step=0.01)
            page_count = st.number_input(
                "Page count", min_value=1, value=_number_default(book.page_count if book else None), step=1
            )
        with third:
            rating = st.number_input(
                "Rating", min_value=0.0, max_value=5.0, value=_number_default(book.rating if book else None), step=0.1
            )
            review_count = st.number_input(
                "Review count", min_value=0, value=_number_default(book.review_count if book else None), step=1
            )
            best_seller_rank = st.number_input(
                "Best Seller Rank", min_value=1, value=_number_default(book.best_seller_rank if book else None), step=1
            )
        source_col, id_col, asin_col = st.columns(3)
        with source_col:
            source = st.text_input("Source", value=book.source if book else "manual", max_chars=50)
        with id_col:
            source_identifier = st.text_input(
                "Source identifier", value=book.source_identifier or "" if book else "", max_chars=160,
                help="Required if reviews will reference this book during import.",
            )
        with asin_col:
            asin = st.text_input("ASIN, if known", value=book.asin or "" if book else "", max_chars=20)
        category = st.text_input("Category", value=book.category or "" if book else "", max_chars=250)
        product_reference = st.text_input(
            "Product URL or reference", value=book.product_reference or "" if book else ""
        )
        description = st.text_area("Description", value=book.description or "" if book else "")
        notes = st.text_area("Notes", value=book.notes or "" if book else "")
        submitted = st.form_submit_button(
            "Update book" if book else "Add book",
            type="primary",
            icon=":material/save:" if book else ":material/library_add:",
        )
    return submitted, {
        "source": source,
        "source_identifier": source_identifier,
        "asin": asin,
        "title": title,
        "subtitle": subtitle,
        "author": author,
        "publisher": publisher,
        "publication_date": publication_date,
        "format": None if book_format == "Not specified" else book_format,
        "price": price,
        "page_count": page_count,
        "rating": rating,
        "review_count": review_count,
        "best_seller_rank": best_seller_rank,
        "category": category,
        "product_reference": product_reference,
        "description": description,
        "notes": notes,
    }


def render_manual_book(niches: list[Niche]) -> None:
    st.subheader("Add or edit a competitor")
    niche = select_niche(niches, key="manual_book_niche")
    if niche is None:
        return
    action = st.segmented_control(
        "Action", ("Add book", "Edit book"), default="Add book", required=True, key="manual_book_action"
    )
    book: Book | None = None
    if action == "Edit book":
        with session_scope() as session:
            books = BookRepository(session).list_by_niche(niche.id)
        if not books:
            st.info("This niche has no books to edit.")
            return
        by_id = {item.id: item for item in books}
        selected_id = st.selectbox(
            "Book", list(by_id), format_func=lambda book_id: by_id[book_id].title, key="manual_edit_book"
        )
        book = by_id[selected_id]

    submitted, values = _book_form_values(book, f"book_{book.id if book else 'new'}")
    if submitted:
        try:
            value = BookInput.model_validate(values)
            with session_scope() as session:
                service = BookService(session)
                saved = service.update(book_id=book.id, value=value) if book else service.create(
                    niche_id=niche.id, value=value
                )
            st.success(f"Saved {saved.title}.")
        except (ValidationError, ValueError) as exc:
            render_operation_error(
                exc,
                operation="book.save",
                summary="The competitor record was not saved.",
                recovery="Review the required and numeric fields, then try again.",
                context={
                    "action": "update" if book else "create",
                    "book_id": book.id if book else None,
                    "niche_id": niche.id,
                },
                expected=True,
            )


def _template_buttons(entity: Literal["book", "review"]) -> None:
    if entity == "book":
        csv_data, json_data = BOOKS_CSV_TEMPLATE, BOOKS_JSON_TEMPLATE
        stem = "books"
    else:
        csv_data, json_data = REVIEWS_CSV_TEMPLATE, REVIEWS_JSON_TEMPLATE
        stem = "reviews"
    with st.container(horizontal=True):
        st.download_button(
            "CSV template", csv_data, file_name=f"{stem}_template.csv", mime="text/csv",
            icon=":material/download:", on_click="ignore",
        )
        st.download_button(
            "JSON template", json_data, file_name=f"{stem}_template.json", mime="application/json",
            icon=":material/download:", on_click="ignore",
        )


def _show_preview(preview: ImportPreview[Any]) -> None:
    first, second, third = st.columns(3)
    first.metric("Rows processed", preview.processed_count)
    second.metric("Ready to import", preview.valid_count)
    third.metric("Rejected", preview.rejected_count)
    if preview.valid_rows:
        st.caption("Validated rows")
        st.dataframe(pd.DataFrame(preview.preview_rows()), hide_index=True, key=f"{preview.entity_type}_preview")
    if preview.issues:
        st.caption("Rows requiring attention")
        issues = pd.DataFrame(issue.model_dump(mode="json") for issue in preview.issues)
        st.dataframe(issues, hide_index=True, key=f"{preview.entity_type}_issues")


def render_import(niches: list[Niche], entity: Literal["book", "review"]) -> None:
    label = "books" if entity == "book" else "reviews"
    st.subheader(f"Import {label}")
    niche = select_niche(niches, key=f"import_{entity}_niche")
    if niche is None:
        return
    _template_buttons(entity)
    method = st.segmented_control(
        "Input method", ("Upload file", "Paste CSV"), default="Upload file", required=True,
        key=f"{entity}_input_method",
    )
    content: bytes | None = None
    filename = ""
    file_format = "csv"
    if method == "Upload file":
        upload = st.file_uploader(
            f"Choose a {label} file", type=("csv", "json"), key=f"{entity}_upload", max_upload_size=20
        )
        if upload is not None:
            content = upload.getvalue()
            filename = upload.name
            file_format = upload.name.rsplit(".", 1)[-1].lower()
    else:
        pasted = st.text_area(
            f"Paste {label} CSV", height=180, key=f"{entity}_pasted_csv",
            placeholder=(BOOKS_CSV_TEMPLATE if entity == "book" else REVIEWS_CSV_TEMPLATE).splitlines()[0],
        )
        if pasted.strip():
            content = pasted.encode("utf-8")
            filename = f"pasted_{label}.csv"

    pending_key = f"pending_{entity}_import"
    preview_requested = st.button(
        "Validate and preview", icon=":material/fact_check:", key=f"preview_{entity}", disabled=content is None
    )
    if preview_requested and content is not None:
        st.session_state[pending_key] = {
            "niche_id": niche.id,
            "content": content,
            "filename": filename,
            "file_format": file_format,
        }

    pending = st.session_state.get(pending_key)
    if not pending or pending["niche_id"] != niche.id:
        return
    try:
        with session_scope() as session:
            service = ImportService(session)
            preview = (
                service.prepare_books(**pending)
                if entity == "book"
                else service.prepare_reviews(**pending)
            )
    except Exception as exc:
        render_operation_error(
            exc,
            operation="import.preview",
            summary=f"The {label} file could not be validated.",
            recovery="No records were imported. Check the file and database, then try again.",
            context={"entity": entity, "niche_id": niche.id},
        )
        return
    if preview_requested:
        log_event(
            "import_validation_completed",
            operation="import.preview",
            context={
                "entity": entity,
                "niche_id": niche.id,
                "record_count": preview.valid_count,
                "rejected_count": preview.rejected_count,
                "status": "ready" if preview.valid_count else "rejected",
            },
        )
    st.divider()
    _show_preview(preview)
    if st.button(
        f"Import {preview.valid_count} valid {label}", type="primary", icon=":material/upload:",
        key=f"commit_{entity}", disabled=not preview.valid_rows,
    ):
        try:
            with session_scope() as session:
                service = ImportService(session)
                fresh_preview = (
                    service.prepare_books(**pending)
                    if entity == "book"
                    else service.prepare_reviews(**pending)
                )
                result = (
                    service.import_books(niche_id=niche.id, preview=fresh_preview)
                    if entity == "book"
                    else service.import_reviews(preview=fresh_preview)
                )
        except Exception as exc:
            render_operation_error(
                exc,
                operation="import.commit",
                summary=f"The {label} import was not saved.",
                recovery="The transaction was rolled back. Revalidate the file and try again.",
                context={"entity": entity, "niche_id": niche.id},
            )
        else:
            log_event(
                "import_completed",
                operation="import.commit",
                context={
                    "batch_id": result.batch_id,
                    "entity": entity,
                    "niche_id": niche.id,
                    "record_count": result.imported_count,
                    "rejected_count": result.rejected_count,
                    "status": result.status,
                },
            )
            st.session_state["phase2_import_flash"] = result.model_dump(mode="json")
            del st.session_state[pending_key]
            st.rerun()
