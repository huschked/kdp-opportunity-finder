"""Normalized SQLAlchemy entities for research data and derived evidence."""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class NicheStatus(StrEnum):
    DISCOVERED = "discovered"
    RESEARCHING = "researching"
    PROMISING = "promising"
    VALIDATION = "validation"
    PRODUCTION = "production"
    PUBLISHED = "published"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class Niche(TimestampMixin, Base):
    __tablename__ = "niches"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(250), unique=True, index=True)
    seed_keyword: Mapped[str] = mapped_column(String(250), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default=NicheStatus.DISCOVERED.value, index=True)
    notes: Mapped[str | None] = mapped_column(Text)

    books: Mapped[list[Book]] = relationship(back_populates="niche", cascade="all, delete-orphan")
    pain_points: Mapped[list[PainPoint]] = relationship(back_populates="niche", cascade="all, delete-orphan")
    praise_features: Mapped[list[PraiseFeature]] = relationship(back_populates="niche", cascade="all, delete-orphan")
    analysis_runs: Mapped[list[AnalysisRun]] = relationship(back_populates="niche", cascade="all, delete-orphan")
    score_snapshots: Mapped[list[ScoreSnapshot]] = relationship(back_populates="niche", cascade="all, delete-orphan")
    book_concepts: Mapped[list[BookConcept]] = relationship(back_populates="niche", cascade="all, delete-orphan")


class DataSource(Base):
    __tablename__ = "data_sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_type: Mapped[str] = mapped_column(String(50), index=True)
    name: Mapped[str] = mapped_column(String(250))
    reference: Mapped[str | None] = mapped_column(Text)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    checksum: Mapped[str | None] = mapped_column(String(128))
    notes: Mapped[str | None] = mapped_column(Text)


class ImportBatch(Base):
    __tablename__ = "import_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(30))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processed_count: Mapped[int] = mapped_column(Integer, default=0)
    imported_count: Mapped[int] = mapped_column(Integer, default=0)
    rejected_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    errors_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)


class Book(TimestampMixin, Base):
    __tablename__ = "books"
    __table_args__ = (
        UniqueConstraint("source", "source_identifier", name="uq_book_source_identifier"),
        CheckConstraint("rating IS NULL OR (rating >= 0 AND rating <= 5)", name="ck_book_rating"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    niche_id: Mapped[int] = mapped_column(ForeignKey("niches.id"), index=True)
    data_source_id: Mapped[int | None] = mapped_column(ForeignKey("data_sources.id"))
    source: Mapped[str] = mapped_column(String(50), default="manual")
    source_identifier: Mapped[str | None] = mapped_column(String(160), index=True)
    asin: Mapped[str | None] = mapped_column(String(20), index=True)
    title: Mapped[str] = mapped_column(String(500))
    subtitle: Mapped[str | None] = mapped_column(String(500))
    author: Mapped[str | None] = mapped_column(String(250))
    publisher: Mapped[str | None] = mapped_column(String(250))
    publication_date: Mapped[date | None] = mapped_column(Date)
    format: Mapped[str | None] = mapped_column(String(50))
    price: Mapped[float | None] = mapped_column(Float)
    page_count: Mapped[int | None] = mapped_column(Integer)
    rating: Mapped[float | None] = mapped_column(Float)
    review_count: Mapped[int | None] = mapped_column(Integer)
    best_seller_rank: Mapped[int | None] = mapped_column(Integer)
    category: Mapped[str | None] = mapped_column(String(250))
    product_reference: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    cover_image_reference: Mapped[str | None] = mapped_column(Text)
    date_collected: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    notes: Mapped[str | None] = mapped_column(Text)

    niche: Mapped[Niche] = relationship(back_populates="books")
    reviews: Mapped[list[Review]] = relationship(back_populates="book", cascade="all, delete-orphan")
    market_snapshots: Mapped[list[MarketSnapshot]] = relationship(back_populates="book", cascade="all, delete-orphan")


class MarketSnapshot(Base):
    __tablename__ = "market_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    price: Mapped[float | None] = mapped_column(Float)
    rating: Mapped[float | None] = mapped_column(Float)
    review_count: Mapped[int | None] = mapped_column(Integer)
    best_seller_rank: Mapped[int | None] = mapped_column(Integer)
    raw_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    book: Mapped[Book] = relationship(back_populates="market_snapshots")


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (
        UniqueConstraint("book_id", "normalized_hash", name="uq_review_book_hash"),
        CheckConstraint("rating IS NULL OR (rating >= 1 AND rating <= 5)", name="ck_review_rating"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"), index=True)
    data_source_id: Mapped[int | None] = mapped_column(ForeignKey("data_sources.id"))
    source: Mapped[str] = mapped_column(String(50), default="manual")
    source_review_identifier: Mapped[str | None] = mapped_column(String(160), index=True)
    rating: Mapped[int | None] = mapped_column(Integer, index=True)
    title: Mapped[str | None] = mapped_column(String(500))
    raw_body: Mapped[str] = mapped_column(Text)
    normalized_body: Mapped[str] = mapped_column(Text)
    normalized_hash: Mapped[str] = mapped_column(String(64), index=True)
    review_date: Mapped[date | None] = mapped_column(Date)
    verified_purchase: Mapped[bool | None] = mapped_column(Boolean)
    helpful_votes: Mapped[int | None] = mapped_column(Integer)
    date_collected: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    book: Mapped[Book] = relationship(back_populates="reviews")
    analysis: Mapped[ReviewAnalysis | None] = relationship(back_populates="review", cascade="all, delete-orphan", uselist=False)
    pain_point_links: Mapped[list[ReviewPainPoint]] = relationship(back_populates="review", cascade="all, delete-orphan")
    praise_links: Mapped[list[ReviewPraiseFeature]] = relationship(back_populates="review", cascade="all, delete-orphan")


class ReviewAnalysis(Base):
    __tablename__ = "review_analyses"

    id: Mapped[int] = mapped_column(primary_key=True)
    review_id: Mapped[int] = mapped_column(ForeignKey("reviews.id"), unique=True, index=True)
    analysis_run_id: Mapped[int | None] = mapped_column(ForeignKey("analysis_runs.id"))
    sentiment: Mapped[str | None] = mapped_column(String(30), index=True)
    topics_json: Mapped[list[str] | None] = mapped_column(JSON)
    features_json: Mapped[list[str] | None] = mapped_column(JSON)
    desired_outcomes_json: Mapped[list[str] | None] = mapped_column(JSON)
    reader_skill_level: Mapped[str | None] = mapped_column(String(50))
    purchase_motivation: Mapped[str | None] = mapped_column(Text)
    result_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    schema_version: Mapped[str] = mapped_column(String(30), default="1")
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    review: Mapped[Review] = relationship(back_populates="analysis")


class PainPoint(TimestampMixin, Base):
    __tablename__ = "pain_points"
    __table_args__ = (UniqueConstraint("niche_id", "canonical_name", name="uq_pain_niche_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    niche_id: Mapped[int] = mapped_column(ForeignKey("niches.id"), index=True)
    canonical_name: Mapped[str] = mapped_column(String(250))
    description: Mapped[str | None] = mapped_column(Text)
    system_solvability_score: Mapped[float | None] = mapped_column(Float)
    human_solvability_score: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[float | None] = mapped_column(Float)
    suggested_solution: Mapped[str | None] = mapped_column(Text)

    niche: Mapped[Niche] = relationship(back_populates="pain_points")
    review_links: Mapped[list[ReviewPainPoint]] = relationship(back_populates="pain_point", cascade="all, delete-orphan")


class ReviewPainPoint(Base):
    __tablename__ = "review_pain_points"
    __table_args__ = (UniqueConstraint("review_id", "pain_point_id", name="uq_review_pain"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    review_id: Mapped[int] = mapped_column(ForeignKey("reviews.id"), index=True)
    pain_point_id: Mapped[int] = mapped_column(ForeignKey("pain_points.id"), index=True)
    severity: Mapped[float] = mapped_column(Float)
    solvable: Mapped[bool] = mapped_column(Boolean)
    extraction_text: Mapped[str | None] = mapped_column(Text)
    extraction_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    review: Mapped[Review] = relationship(back_populates="pain_point_links")
    pain_point: Mapped[PainPoint] = relationship(back_populates="review_links")


class PraiseFeature(TimestampMixin, Base):
    __tablename__ = "praise_features"
    __table_args__ = (UniqueConstraint("niche_id", "canonical_name", name="uq_praise_niche_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    niche_id: Mapped[int] = mapped_column(ForeignKey("niches.id"), index=True)
    canonical_name: Mapped[str] = mapped_column(String(250))
    description: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float)

    niche: Mapped[Niche] = relationship(back_populates="praise_features")
    review_links: Mapped[list[ReviewPraiseFeature]] = relationship(back_populates="praise_feature", cascade="all, delete-orphan")


class ReviewPraiseFeature(Base):
    __tablename__ = "review_praise_features"
    __table_args__ = (UniqueConstraint("review_id", "praise_feature_id", name="uq_review_praise"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    review_id: Mapped[int] = mapped_column(ForeignKey("reviews.id"), index=True)
    praise_feature_id: Mapped[int] = mapped_column(ForeignKey("praise_features.id"), index=True)
    strength: Mapped[float] = mapped_column(Float)
    extraction_text: Mapped[str | None] = mapped_column(Text)

    review: Mapped[Review] = relationship(back_populates="praise_links")
    praise_feature: Mapped[PraiseFeature] = relationship(back_populates="review_links")


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    niche_id: Mapped[int] = mapped_column(ForeignKey("niches.id"), index=True)
    analysis_type: Mapped[str] = mapped_column(String(50), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider: Mapped[str | None] = mapped_column(String(80))
    model: Mapped[str | None] = mapped_column(String(120))
    prompt_version: Mapped[str | None] = mapped_column(String(50))
    parameters_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    result_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    estimated_cost_usd: Mapped[float | None] = mapped_column(Float)

    niche: Mapped[Niche] = relationship(back_populates="analysis_runs")


class ScoreSnapshot(Base):
    __tablename__ = "score_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    niche_id: Mapped[int] = mapped_column(ForeignKey("niches.id"), index=True)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    scoring_version: Mapped[str] = mapped_column(String(30))
    demand_score: Mapped[float] = mapped_column(Float)
    competition_score: Mapped[float] = mapped_column(Float)
    customer_gap_score: Mapped[float] = mapped_column(Float)
    economics_score: Mapped[float] = mapped_column(Float)
    ai_suitability_score: Mapped[float] = mapped_column(Float)
    expansion_score: Mapped[float] = mapped_column(Float)
    automated_overall_score: Mapped[float] = mapped_column(Float)
    human_overall_score: Mapped[float | None] = mapped_column(Float)
    confidence_score: Mapped[float] = mapped_column(Float)
    unmet_demand_index: Mapped[float | None] = mapped_column(Float)
    weights_json: Mapped[dict[str, float]] = mapped_column(JSON)
    explanation_json: Mapped[dict[str, Any]] = mapped_column(JSON)

    niche: Mapped[Niche] = relationship(back_populates="score_snapshots")


class BookConcept(Base):
    __tablename__ = "book_concepts"

    id: Mapped[int] = mapped_column(primary_key=True)
    niche_id: Mapped[int] = mapped_column(ForeignKey("niches.id"), index=True)
    analysis_run_id: Mapped[int | None] = mapped_column(ForeignKey("analysis_runs.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    title: Mapped[str | None] = mapped_column(String(500))
    concept_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    evidence_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON)

    niche: Mapped[Niche] = relationship(back_populates="book_concepts")
