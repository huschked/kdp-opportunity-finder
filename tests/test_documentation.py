from pathlib import Path
import re

from collectors import parse_records
from collectors.templates import (
    BOOKS_CSV_TEMPLATE,
    BOOKS_JSON_TEMPLATE,
    REVIEWS_CSV_TEMPLATE,
    REVIEWS_JSON_TEMPLATE,
)
from models.schemas import BookInput, ReviewInput


ROOT = Path(__file__).resolve().parents[1]
MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def test_root_documentation_links_resolve() -> None:
    for document in ROOT.glob("*.md"):
        for target in MARKDOWN_LINK.findall(document.read_text(encoding="utf-8")):
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            relative_path = target.split("#", 1)[0]
            assert (document.parent / relative_path).is_file(), (
                f"{document.name} links to missing file {relative_path}"
            )


def test_import_reference_covers_current_schema_fields_and_aliases() -> None:
    reference = (ROOT / "IMPORT_REFERENCE.md").read_text(encoding="utf-8")
    book_section, review_section = reference.split("## Review fields", maxsplit=1)

    for field_name in BookInput.model_fields:
        assert f"`{field_name}`" in book_section
    for alias in ("bsr", "product_url", "cover_image_url"):
        assert f"`{alias}`" in book_section
    for field_name in ReviewInput.model_fields:
        assert f"`{field_name}`" in review_section


def test_downloadable_import_templates_match_validation_contracts() -> None:
    template_cases = (
        (BOOKS_CSV_TEMPLATE, "csv", "books", BookInput),
        (BOOKS_JSON_TEMPLATE, "json", "books", BookInput),
        (REVIEWS_CSV_TEMPLATE, "csv", "reviews", ReviewInput),
        (REVIEWS_JSON_TEMPLATE, "json", "reviews", ReviewInput),
    )

    for content, file_format, root_key, model in template_cases:
        records = parse_records(content.encode("utf-8"), file_format, root_key=root_key)
        assert records
        for record in records:
            model.model_validate(record.values)
