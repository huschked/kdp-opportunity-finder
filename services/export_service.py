"""Traceable CSV and JSON exports for stored research and decisions."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime, timezone
import io
import json
import re
from typing import Any, Mapping

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import (
    Book,
    DataSource,
    MarketSnapshot,
    Niche,
    Review,
    ReviewAnalysis,
    ReviewPainPoint,
    ReviewPraiseFeature,
    ScoreSnapshot,
)
from services.comparison_service import compare_niches


DECISIONS_EXPORT = "decisions"
BOOKS_EXPORT = "books"
REVIEWS_EXPORT = "reviews"
EXPORT_TYPES = (DECISIONS_EXPORT, BOOKS_EXPORT, REVIEWS_EXPORT)
EXPORT_LABELS = {
    DECISIONS_EXPORT: "Niche decisions",
    BOOKS_EXPORT: "Competitor books",
    REVIEWS_EXPORT: "Review evidence",
}
EXPORT_DESCRIPTIONS = {
    DECISIONS_EXPORT: "Latest immutable score snapshot for each niche in scope.",
    BOOKS_EXPORT: "Stored competitor observations with source and latest market-snapshot provenance.",
    REVIEWS_EXPORT: "Raw review evidence, analysis metadata, and links to derived pain and praise records.",
}
MISSING_VALUE_POLICY = (
    "Missing values remain blank in CSV and null in JSON; no marketplace value is estimated or filled."
)


DECISION_COLUMNS = (
    "niche_id",
    "niche_name",
    "seed_keyword",
    "status",
    "niche_description",
    "niche_notes",
    "niche_updated_at",
    "decision_rank",
    "score_snapshot_id",
    "score_calculated_at",
    "scoring_version",
    "demand_score",
    "competition_score",
    "customer_gap_score",
    "economics_score",
    "ai_suitability_score",
    "expansion_score",
    "automated_score",
    "human_adjusted_score",
    "decision_score",
    "confidence_score",
    "unmet_demand_index",
    "recommendation",
    "confidence_warnings",
    "missing_observations",
    "book_count",
    "review_count",
    "reviewed_book_count",
    "field_completeness",
    "analysis_completeness",
    "weights",
    "explanation",
)

BOOK_COLUMNS = (
    "book_id",
    "niche_id",
    "niche_name",
    "data_source_id",
    "data_source_type",
    "data_source_name",
    "data_source_reference",
    "data_source_collected_at",
    "data_source_checksum",
    "source",
    "source_identifier",
    "asin",
    "product_reference",
    "title",
    "subtitle",
    "author",
    "publisher",
    "publication_date",
    "format",
    "price",
    "page_count",
    "rating",
    "review_count",
    "best_seller_rank",
    "category",
    "description",
    "cover_image_reference",
    "date_collected",
    "notes",
    "latest_market_snapshot_id",
    "latest_market_observed_at",
    "latest_market_price",
    "latest_market_rating",
    "latest_market_review_count",
    "latest_market_best_seller_rank",
    "latest_market_raw",
    "created_at",
    "updated_at",
)

REVIEW_COLUMNS = (
    "review_id",
    "book_id",
    "book_title",
    "book_source_identifier",
    "niche_id",
    "niche_name",
    "data_source_id",
    "data_source_type",
    "data_source_name",
    "data_source_reference",
    "data_source_collected_at",
    "data_source_checksum",
    "source",
    "source_review_identifier",
    "rating",
    "title",
    "raw_body",
    "normalized_body",
    "normalized_hash",
    "review_date",
    "verified_purchase",
    "helpful_votes",
    "date_collected",
    "review_analysis_id",
    "analysis_run_id",
    "analysis_sentiment",
    "analysis_topics",
    "analysis_features",
    "analysis_desired_outcomes",
    "analysis_reader_skill_level",
    "analysis_purchase_motivation",
    "analysis_schema_version",
    "analysis_content_hash",
    "analysis_result",
    "analyzed_at",
    "pain_point_links",
    "praise_feature_links",
)


@dataclass(frozen=True, slots=True)
class ExportNiche:
    niche_id: int
    niche_name: str


@dataclass(frozen=True, slots=True)
class ExportDataset:
    export_type: str
    label: str
    description: str
    scope: Mapping[str, Any]
    filename_stem: str
    columns: tuple[str, ...]
    records: tuple[dict[str, Any], ...]
    dataset_warnings: tuple[str, ...]
    generated_at: datetime

    @property
    def record_count(self) -> int:
        return len(self.records)

    def filename(self, extension: str) -> str:
        normalized = extension.lower().lstrip(".")
        if normalized not in {"csv", "json"}:
            raise ValueError("Export extension must be csv or json")
        return f"{self.filename_stem}.{normalized}"


def list_export_niches(session: Session) -> tuple[ExportNiche, ...]:
    """Return stable niche choices for the export page."""

    return tuple(
        ExportNiche(niche_id=niche.id, niche_name=niche.name)
        for niche in session.scalars(select(Niche).order_by(Niche.name, Niche.id))
    )


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return (slug or "niche")[:60].rstrip("-")


def _require_niche(session: Session, niche_id: int) -> Niche:
    niche = session.get(Niche, niche_id)
    if niche is None:
        raise ValueError(f"Niche {niche_id} does not exist")
    return niche


def _latest_market_snapshots(
    session: Session,
    book_ids: list[int],
) -> dict[int, MarketSnapshot]:
    if not book_ids:
        return {}
    snapshots = session.scalars(
        select(MarketSnapshot)
        .where(MarketSnapshot.book_id.in_(book_ids))
        .order_by(
            MarketSnapshot.book_id,
            MarketSnapshot.observed_at.desc(),
            MarketSnapshot.id.desc(),
        )
    )
    latest: dict[int, MarketSnapshot] = {}
    for snapshot in snapshots:
        latest.setdefault(snapshot.book_id, snapshot)
    return latest


def _decision_dataset(
    session: Session,
    *,
    niche_id: int | None,
    generated_at: datetime,
) -> ExportDataset:
    statement = select(Niche).order_by(Niche.name, Niche.id)
    selected_niche: Niche | None = None
    if niche_id is not None:
        selected_niche = _require_niche(session, niche_id)
        statement = statement.where(Niche.id == niche_id)
    niches = list(session.scalars(statement))
    niche_by_id = {niche.id: niche for niche in niches}
    comparison = compare_niches(session, [niche.id for niche in niches])

    snapshot_ids = [row.snapshot_id for row in comparison.rows if row.snapshot_id is not None]
    snapshots = (
        {
            snapshot.id: snapshot
            for snapshot in session.scalars(
                select(ScoreSnapshot).where(ScoreSnapshot.id.in_(snapshot_ids))
            )
        }
        if snapshot_ids
        else {}
    )

    records: list[dict[str, Any]] = []
    for row in comparison.rows:
        niche = niche_by_id[row.niche_id]
        snapshot = snapshots.get(row.snapshot_id)
        records.append(
            {
                "niche_id": niche.id,
                "niche_name": niche.name,
                "seed_keyword": niche.seed_keyword,
                "status": niche.status,
                "niche_description": niche.description,
                "niche_notes": niche.notes,
                "niche_updated_at": niche.updated_at,
                "decision_rank": row.rank,
                "score_snapshot_id": row.snapshot_id,
                "score_calculated_at": row.calculated_at,
                "scoring_version": row.scoring_version,
                "demand_score": row.components["demand"],
                "competition_score": row.components["competition"],
                "customer_gap_score": row.components["customer_gap"],
                "economics_score": row.components["economics"],
                "ai_suitability_score": row.components["ai_suitability"],
                "expansion_score": row.components["expansion"],
                "automated_score": row.automated_score,
                "human_adjusted_score": row.human_adjusted_score,
                "decision_score": row.decision_score,
                "confidence_score": row.confidence,
                "unmet_demand_index": row.unmet_demand_index,
                "recommendation": row.recommendation,
                "confidence_warnings": list(row.warnings),
                "missing_observations": list(row.missing_observations),
                "book_count": row.book_count,
                "review_count": row.review_count,
                "reviewed_book_count": row.reviewed_book_count,
                "field_completeness": row.field_completeness,
                "analysis_completeness": row.analysis_completeness,
                "weights": dict(snapshot.weights_json or {}) if snapshot else None,
                "explanation": dict(snapshot.explanation_json or {}) if snapshot else None,
            }
        )

    if selected_niche is None:
        scope = {"kind": "all_niches", "snapshot_policy": "latest_per_niche"}
        filename_stem = "kdp-niche-decisions-latest-all"
    else:
        scope = {
            "kind": "single_niche",
            "niche_id": selected_niche.id,
            "niche_name": selected_niche.name,
            "snapshot_policy": "latest_for_niche",
        }
        filename_stem = (
            f"kdp-niche-decisions-latest-niche-{selected_niche.id}-{_slug(selected_niche.name)}"
        )
    warnings = list(comparison.coverage_warnings)
    if not records:
        warnings.append("No niches matched this export scope.")
    return ExportDataset(
        export_type=DECISIONS_EXPORT,
        label=EXPORT_LABELS[DECISIONS_EXPORT],
        description=EXPORT_DESCRIPTIONS[DECISIONS_EXPORT],
        scope=scope,
        filename_stem=filename_stem,
        columns=DECISION_COLUMNS,
        records=tuple(records),
        dataset_warnings=tuple(warnings),
        generated_at=generated_at,
    )


def _book_dataset(
    session: Session,
    *,
    niche_id: int,
    generated_at: datetime,
) -> ExportDataset:
    niche = _require_niche(session, niche_id)
    rows = list(
        session.execute(
            select(Book, DataSource)
            .outerjoin(DataSource, DataSource.id == Book.data_source_id)
            .where(Book.niche_id == niche_id)
            .order_by(Book.title, Book.id)
        )
    )
    snapshots = _latest_market_snapshots(session, [book.id for book, _source in rows])
    records: list[dict[str, Any]] = []
    for book, source in rows:
        snapshot = snapshots.get(book.id)
        records.append(
            {
                "book_id": book.id,
                "niche_id": niche.id,
                "niche_name": niche.name,
                "data_source_id": source.id if source else None,
                "data_source_type": source.source_type if source else None,
                "data_source_name": source.name if source else None,
                "data_source_reference": source.reference if source else None,
                "data_source_collected_at": source.collected_at if source else None,
                "data_source_checksum": source.checksum if source else None,
                "source": book.source,
                "source_identifier": book.source_identifier,
                "asin": book.asin,
                "product_reference": book.product_reference,
                "title": book.title,
                "subtitle": book.subtitle,
                "author": book.author,
                "publisher": book.publisher,
                "publication_date": book.publication_date,
                "format": book.format,
                "price": book.price,
                "page_count": book.page_count,
                "rating": book.rating,
                "review_count": book.review_count,
                "best_seller_rank": book.best_seller_rank,
                "category": book.category,
                "description": book.description,
                "cover_image_reference": book.cover_image_reference,
                "date_collected": book.date_collected,
                "notes": book.notes,
                "latest_market_snapshot_id": snapshot.id if snapshot else None,
                "latest_market_observed_at": snapshot.observed_at if snapshot else None,
                "latest_market_price": snapshot.price if snapshot else None,
                "latest_market_rating": snapshot.rating if snapshot else None,
                "latest_market_review_count": snapshot.review_count if snapshot else None,
                "latest_market_best_seller_rank": (
                    snapshot.best_seller_rank if snapshot else None
                ),
                "latest_market_raw": snapshot.raw_json if snapshot else None,
                "created_at": book.created_at,
                "updated_at": book.updated_at,
            }
        )
    warnings = () if records else ("No competitor books matched this export scope.",)
    return ExportDataset(
        export_type=BOOKS_EXPORT,
        label=EXPORT_LABELS[BOOKS_EXPORT],
        description=EXPORT_DESCRIPTIONS[BOOKS_EXPORT],
        scope={"kind": "single_niche", "niche_id": niche.id, "niche_name": niche.name},
        filename_stem=f"kdp-competitor-books-niche-{niche.id}-{_slug(niche.name)}",
        columns=BOOK_COLUMNS,
        records=tuple(records),
        dataset_warnings=warnings,
        generated_at=generated_at,
    )


def _review_dataset(
    session: Session,
    *,
    niche_id: int,
    generated_at: datetime,
) -> ExportDataset:
    niche = _require_niche(session, niche_id)
    rows = list(
        session.execute(
            select(Review, Book, DataSource, ReviewAnalysis)
            .join(Book, Book.id == Review.book_id)
            .outerjoin(DataSource, DataSource.id == Review.data_source_id)
            .outerjoin(ReviewAnalysis, ReviewAnalysis.review_id == Review.id)
            .where(Book.niche_id == niche_id)
            .order_by(Book.title, Review.review_date.desc(), Review.id)
        )
    )
    review_ids = [review.id for review, _book, _source, _analysis in rows]
    pain_links_by_review: dict[int, list[dict[str, Any]]] = {}
    praise_links_by_review: dict[int, list[dict[str, Any]]] = {}
    if review_ids:
        for link in session.scalars(
            select(ReviewPainPoint)
            .where(ReviewPainPoint.review_id.in_(review_ids))
            .order_by(ReviewPainPoint.review_id, ReviewPainPoint.id)
        ):
            pain_links_by_review.setdefault(link.review_id, []).append(
                {
                    "review_pain_point_id": link.id,
                    "pain_point_id": link.pain_point_id,
                    "severity": link.severity,
                    "solvable": link.solvable,
                    "extraction_text": link.extraction_text,
                    "extraction": link.extraction_json,
                }
            )
        for link in session.scalars(
            select(ReviewPraiseFeature)
            .where(ReviewPraiseFeature.review_id.in_(review_ids))
            .order_by(ReviewPraiseFeature.review_id, ReviewPraiseFeature.id)
        ):
            praise_links_by_review.setdefault(link.review_id, []).append(
                {
                    "review_praise_feature_id": link.id,
                    "praise_feature_id": link.praise_feature_id,
                    "strength": link.strength,
                    "extraction_text": link.extraction_text,
                }
            )

    records: list[dict[str, Any]] = []
    for review, book, source, analysis in rows:
        records.append(
            {
                "review_id": review.id,
                "book_id": book.id,
                "book_title": book.title,
                "book_source_identifier": book.source_identifier,
                "niche_id": niche.id,
                "niche_name": niche.name,
                "data_source_id": source.id if source else None,
                "data_source_type": source.source_type if source else None,
                "data_source_name": source.name if source else None,
                "data_source_reference": source.reference if source else None,
                "data_source_collected_at": source.collected_at if source else None,
                "data_source_checksum": source.checksum if source else None,
                "source": review.source,
                "source_review_identifier": review.source_review_identifier,
                "rating": review.rating,
                "title": review.title,
                "raw_body": review.raw_body,
                "normalized_body": review.normalized_body,
                "normalized_hash": review.normalized_hash,
                "review_date": review.review_date,
                "verified_purchase": review.verified_purchase,
                "helpful_votes": review.helpful_votes,
                "date_collected": review.date_collected,
                "review_analysis_id": analysis.id if analysis else None,
                "analysis_run_id": analysis.analysis_run_id if analysis else None,
                "analysis_sentiment": analysis.sentiment if analysis else None,
                "analysis_topics": analysis.topics_json if analysis else None,
                "analysis_features": analysis.features_json if analysis else None,
                "analysis_desired_outcomes": (
                    analysis.desired_outcomes_json if analysis else None
                ),
                "analysis_reader_skill_level": (
                    analysis.reader_skill_level if analysis else None
                ),
                "analysis_purchase_motivation": (
                    analysis.purchase_motivation if analysis else None
                ),
                "analysis_schema_version": analysis.schema_version if analysis else None,
                "analysis_content_hash": analysis.content_hash if analysis else None,
                "analysis_result": analysis.result_json if analysis else None,
                "analyzed_at": analysis.analyzed_at if analysis else None,
                "pain_point_links": pain_links_by_review.get(review.id, []),
                "praise_feature_links": praise_links_by_review.get(review.id, []),
            }
        )
    warnings = () if records else ("No reviews matched this export scope.",)
    return ExportDataset(
        export_type=REVIEWS_EXPORT,
        label=EXPORT_LABELS[REVIEWS_EXPORT],
        description=EXPORT_DESCRIPTIONS[REVIEWS_EXPORT],
        scope={"kind": "single_niche", "niche_id": niche.id, "niche_name": niche.name},
        filename_stem=f"kdp-review-evidence-niche-{niche.id}-{_slug(niche.name)}",
        columns=REVIEW_COLUMNS,
        records=tuple(records),
        dataset_warnings=warnings,
        generated_at=generated_at,
    )


def build_export_dataset(
    session: Session,
    *,
    export_type: str,
    niche_id: int | None = None,
    generated_at: datetime | None = None,
) -> ExportDataset:
    """Build one explicitly scoped, in-memory export dataset."""

    if export_type not in EXPORT_TYPES:
        raise ValueError(f"Unsupported export type: {export_type}")
    timestamp = generated_at or datetime.now(timezone.utc)
    if export_type == DECISIONS_EXPORT:
        return _decision_dataset(session, niche_id=niche_id, generated_at=timestamp)
    if niche_id is None:
        raise ValueError(f"A niche is required for the {EXPORT_LABELS[export_type]} export")
    if export_type == BOOKS_EXPORT:
        return _book_dataset(session, niche_id=niche_id, generated_at=timestamp)
    return _review_dataset(session, niche_id=niche_id, generated_at=timestamp)


def _json_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    normalized = _json_value(value)
    if isinstance(normalized, (dict, list)):
        return json.dumps(normalized, ensure_ascii=False, separators=(",", ":"))
    if isinstance(normalized, bool):
        return "true" if normalized else "false"
    return normalized


def render_export_csv(dataset: ExportDataset) -> bytes:
    """Serialize records in declared column order without filling missing values."""

    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=dataset.columns, lineterminator="\n")
    writer.writeheader()
    for record in dataset.records:
        writer.writerow({column: _csv_value(record.get(column)) for column in dataset.columns})
    return output.getvalue().encode("utf-8-sig")


def render_export_json(dataset: ExportDataset) -> bytes:
    """Serialize an export manifest and records with native nulls and nested values."""

    payload = {
        "schema_version": "1.0",
        "export_type": dataset.export_type,
        "label": dataset.label,
        "description": dataset.description,
        "scope": _json_value(dataset.scope),
        "generated_at": dataset.generated_at.isoformat(),
        "record_count": dataset.record_count,
        "columns": list(dataset.columns),
        "dataset_warnings": list(dataset.dataset_warnings),
        "missing_value_policy": MISSING_VALUE_POLICY,
        "records": [
            {column: _json_value(record.get(column)) for column in dataset.columns}
            for record in dataset.records
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")
