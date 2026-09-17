"""Validated transport models for manual entry and batch imports."""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


class ImportModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("*", mode="before")
    @classmethod
    def empty_strings_are_missing(cls, value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            return None
        return value


class BookInput(ImportModel):
    niche: str | None = Field(default=None, exclude=True, max_length=250)
    source: str = "manual"
    source_identifier: str | None = Field(default=None, max_length=160)
    asin: str | None = Field(default=None, max_length=20)
    title: str = Field(min_length=1, max_length=500)
    subtitle: str | None = Field(default=None, max_length=500)
    author: str | None = Field(default=None, max_length=250)
    publisher: str | None = Field(default=None, max_length=250)
    publication_date: date | None = None
    format: str | None = Field(default=None, max_length=50)
    price: float | None = Field(default=None, ge=0)
    page_count: int | None = Field(default=None, ge=1)
    rating: float | None = Field(default=None, ge=0, le=5)
    review_count: int | None = Field(default=None, ge=0)
    best_seller_rank: int | None = Field(
        default=None, ge=1, validation_alias=AliasChoices("best_seller_rank", "bsr")
    )
    category: str | None = Field(default=None, max_length=250)
    product_reference: str | None = Field(
        default=None, validation_alias=AliasChoices("product_reference", "product_url")
    )
    description: str | None = None
    cover_image_reference: str | None = Field(
        default=None,
        validation_alias=AliasChoices("cover_image_reference", "cover_image_url"),
    )
    notes: str | None = None

    @field_validator(
        "niche",
        "source",
        "source_identifier",
        "asin",
        "title",
        "subtitle",
        "author",
        "publisher",
        "format",
        "category",
        "product_reference",
        "description",
        "cover_image_reference",
        "notes",
        mode="after",
    )
    @classmethod
    def strip_text_fields(cls, value: str | None) -> str | None:
        return value.strip() if value else None

    @field_validator("asin")
    @classmethod
    def normalize_asin(cls, value: str | None) -> str | None:
        return value.upper() if value else None


class ReviewInput(ImportModel):
    book_identifier: str = Field(min_length=1, max_length=160)
    source: str = "manual"
    source_review_identifier: str | None = Field(default=None, max_length=160)
    rating: int | None = Field(default=None, ge=1, le=5)
    title: str | None = Field(default=None, max_length=500)
    body: str = Field(min_length=1)
    review_date: date | None = None
    verified_purchase: bool | None = None
    helpful_votes: int | None = Field(default=None, ge=0)

    @field_validator(
        "book_identifier", "source", "source_review_identifier", "title", mode="after"
    )
    @classmethod
    def strip_metadata_fields(cls, value: str | None) -> str | None:
        return value.strip() if value else None


class ImportIssue(BaseModel):
    row_number: int = Field(ge=1)
    field: str | None = None
    reason: str
    value: Any = None


class ImportResult(BaseModel):
    batch_id: int
    processed_count: int
    imported_count: int
    rejected_count: int
    status: str
    issues: list[ImportIssue] = Field(default_factory=list)
