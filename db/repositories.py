"""Small repositories that keep persistence concerns out of the UI."""

from __future__ import annotations

from dataclasses import dataclass

from datetime import date

from sqlalchemy import distinct, func, or_, select
from sqlalchemy.orm import Session

from models import (
    AnalysisRun,
    Book,
    BookConcept,
    Niche,
    PainPoint,
    PraiseFeature,
    Review,
    ReviewAnalysis,
    ReviewPainPoint,
    ReviewPraiseFeature,
    ScoreSnapshot,
)


@dataclass(frozen=True, slots=True)
class DashboardTotals:
    niches: int
    books: int
    reviews: int
    promising: int


class NicheRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        *,
        name: str,
        seed_keyword: str,
        description: str | None = None,
        notes: str | None = None,
    ) -> Niche:
        niche = Niche(
            name=name.strip(),
            seed_keyword=seed_keyword.strip(),
            description=description.strip() if description else None,
            notes=notes.strip() if notes else None,
        )
        self.session.add(niche)
        self.session.flush()
        return niche

    def list_all(self) -> list[Niche]:
        return list(self.session.scalars(select(Niche).order_by(Niche.updated_at.desc())))

    def get(self, niche_id: int) -> Niche | None:
        return self.session.get(Niche, niche_id)


class DashboardRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def totals(self) -> DashboardTotals:
        promising_statuses = ("promising", "validation", "production", "published")
        return DashboardTotals(
            niches=self.session.scalar(select(func.count(Niche.id))) or 0,
            books=self.session.scalar(select(func.count(Book.id))) or 0,
            reviews=self.session.scalar(select(func.count(Review.id))) or 0,
            promising=self.session.scalar(
                select(func.count(Niche.id)).where(Niche.status.in_(promising_statuses))
            ) or 0,
        )

    def latest_scores(self) -> list[dict[str, object]]:
        latest = (
            select(
                ScoreSnapshot.niche_id,
                func.max(ScoreSnapshot.calculated_at).label("calculated_at"),
            )
            .group_by(ScoreSnapshot.niche_id)
            .subquery()
        )
        statement = (
            select(Niche, ScoreSnapshot)
            .join(ScoreSnapshot, ScoreSnapshot.niche_id == Niche.id)
            .join(
                latest,
                (latest.c.niche_id == ScoreSnapshot.niche_id)
                & (latest.c.calculated_at == ScoreSnapshot.calculated_at),
            )
            .order_by(ScoreSnapshot.automated_overall_score.desc())
        )
        rows = []
        for niche, score in self.session.execute(statement):
            rows.append(
                {
                    "Niche": niche.name,
                    "Opportunity": score.human_overall_score if score.human_overall_score is not None else score.automated_overall_score,
                    "Automated": score.automated_overall_score,
                    "Recommendation": (score.explanation_json or {}).get("recommendation", "Not available"),
                    "Confidence": score.confidence_score,
                    "Demand": score.demand_score,
                    "Competition": score.competition_score,
                    "Customer Gap": score.customer_gap_score,
                    "UDI": score.unmet_demand_index,
                    "Status": niche.status.title(),
                }
            )
        return rows

    def stage_counts(self) -> list[dict[str, object]]:
        statement = select(Niche.status, func.count(Niche.id)).group_by(Niche.status)
        return [
            {"Stage": status.title(), "Count": count}
            for status, count in self.session.execute(statement)
        ]

    def recent_analyses(self, limit: int = 5) -> list[dict[str, object]]:
        statement = (
            select(AnalysisRun, Niche.name)
            .join(Niche, Niche.id == AnalysisRun.niche_id)
            .order_by(AnalysisRun.started_at.desc())
            .limit(limit)
        )
        return [
            {
                "Niche": name,
                "Type": run.analysis_type,
                "Status": run.status,
                "Started": run.started_at,
            }
            for run, name in self.session.execute(statement)
        ]


class BookRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_by_niche(self, niche_id: int) -> list[Book]:
        return list(self.session.scalars(
            select(Book).where(Book.niche_id == niche_id).order_by(Book.review_count.desc().nullslast(), Book.title)
        ))

    def get(self, book_id: int) -> Book | None:
        return self.session.get(Book, book_id)

    def rows_by_niche(self, niche_id: int) -> list[dict[str, object]]:
        return [
            {
                "id": book.id,
                "title": book.title,
                "author": book.author,
                "price": book.price,
                "rating": book.rating,
                "review_count": book.review_count,
                "best_seller_rank": book.best_seller_rank,
                "page_count": book.page_count,
                "publication_date": book.publication_date,
                "format": book.format,
                "publisher": book.publisher,
                "source_identifier": book.source_identifier,
            }
            for book in self.list_by_niche(niche_id)
        ]


class ScoreRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def latest_for_niche(self, niche_id: int) -> ScoreSnapshot | None:
        return self.session.scalar(
            select(ScoreSnapshot)
            .where(ScoreSnapshot.niche_id == niche_id)
            .order_by(ScoreSnapshot.calculated_at.desc(), ScoreSnapshot.id.desc())
            .limit(1)
        )

    def get(self, snapshot_id: int) -> ScoreSnapshot | None:
        return self.session.get(ScoreSnapshot, snapshot_id)

    def history_for_niche(self, niche_id: int) -> list[ScoreSnapshot]:
        return list(self.session.scalars(
            select(ScoreSnapshot)
            .where(ScoreSnapshot.niche_id == niche_id)
            .order_by(ScoreSnapshot.calculated_at.desc(), ScoreSnapshot.id.desc())
        ))


class ConceptRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def latest_for_niche(self, niche_id: int) -> BookConcept | None:
        return self.session.scalar(
            select(BookConcept)
            .where(BookConcept.niche_id == niche_id)
            .order_by(BookConcept.created_at.desc(), BookConcept.id.desc())
            .limit(1)
        )

    def history_for_niche(self, niche_id: int) -> list[BookConcept]:
        return list(self.session.scalars(
            select(BookConcept)
            .where(BookConcept.niche_id == niche_id)
            .order_by(BookConcept.created_at.desc(), BookConcept.id.desc())
        ))


class ReviewRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def search(
        self,
        *,
        niche_id: int,
        book_id: int | None = None,
        ratings: list[int] | None = None,
        query: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        sentiments: list[str] | None = None,
        topic: str | None = None,
        pain_point_id: int | None = None,
    ) -> list[dict[str, object]]:
        statement = (
            select(Review, Book.title, ReviewAnalysis)
            .join(Book, Book.id == Review.book_id)
            .outerjoin(ReviewAnalysis, ReviewAnalysis.review_id == Review.id)
            .where(
            Book.niche_id == niche_id
            )
        )
        if book_id is not None:
            statement = statement.where(Review.book_id == book_id)
        if ratings:
            statement = statement.where(Review.rating.in_(ratings))
        if query and query.strip():
            term = f"%{query.strip()}%"
            statement = statement.where(or_(
                Review.title.ilike(term),
                Review.normalized_body.ilike(term),
            ))
        if date_from:
            statement = statement.where(Review.review_date >= date_from)
        if date_to:
            statement = statement.where(Review.review_date <= date_to)
        if sentiments:
            statement = statement.where(ReviewAnalysis.sentiment.in_(sentiments))
        if pain_point_id is not None:
            statement = statement.join(ReviewPainPoint, ReviewPainPoint.review_id == Review.id).where(
                ReviewPainPoint.pain_point_id == pain_point_id
            )
        statement = statement.order_by(Review.review_date.desc().nullslast(), Review.id.desc())
        rows = [
            {
                "id": review.id,
                "book": book_title,
                "rating": review.rating,
                "title": review.title,
                "review_date": review.review_date,
                "body": review.raw_body,
                "normalized_body": review.normalized_body,
                "source": review.source,
                "source_review_identifier": review.source_review_identifier,
                "verified_purchase": review.verified_purchase,
                "helpful_votes": review.helpful_votes,
                "sentiment": analysis.sentiment if analysis else None,
                "topics": analysis.topics_json or [] if analysis else [],
                "features": analysis.features_json or [] if analysis else [],
            }
            for review, book_title, analysis in self.session.execute(statement).unique()
        ]
        if topic:
            rows = [row for row in rows if topic in row["topics"]]
        return rows

    def count_by_niche(self, niche_id: int) -> int:
        return self.session.scalar(
            select(func.count(Review.id))
            .join(Book, Book.id == Review.book_id)
            .where(Book.niche_id == niche_id)
        ) or 0

    def analysis_count_by_niche(self, niche_id: int) -> int:
        return self.session.scalar(
            select(func.count(ReviewAnalysis.id))
            .join(Review, Review.id == ReviewAnalysis.review_id)
            .join(Book, Book.id == Review.book_id)
            .where(Book.niche_id == niche_id)
        ) or 0

    def analysis_filter_options(self, niche_id: int) -> dict[str, object]:
        analyses = list(self.session.scalars(
            select(ReviewAnalysis)
            .join(Review, Review.id == ReviewAnalysis.review_id)
            .join(Book, Book.id == Review.book_id)
            .where(Book.niche_id == niche_id)
        ))
        pain_points = list(self.session.scalars(
            select(PainPoint)
            .join(ReviewPainPoint, ReviewPainPoint.pain_point_id == PainPoint.id)
            .join(Review, Review.id == ReviewPainPoint.review_id)
            .join(Book, Book.id == Review.book_id)
            .where(PainPoint.niche_id == niche_id, Book.niche_id == niche_id)
            .distinct()
            .order_by(PainPoint.canonical_name)
        ))
        return {
            "sentiments": sorted({item.sentiment for item in analyses if item.sentiment}),
            "topics": sorted({topic for item in analyses for topic in (item.topics_json or [])}),
            "pain_points": pain_points,
        }


class EvidenceRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def pain_point_summaries(self, niche_id: int) -> list[dict[str, object]]:
        statement = (
            select(
                PainPoint,
                func.count(distinct(ReviewPainPoint.review_id)),
                func.count(distinct(Review.book_id)),
                func.avg(ReviewPainPoint.severity),
            )
            .join(ReviewPainPoint, ReviewPainPoint.pain_point_id == PainPoint.id)
            .join(Review, Review.id == ReviewPainPoint.review_id)
            .where(PainPoint.niche_id == niche_id)
            .group_by(PainPoint.id)
            .order_by(func.count(distinct(ReviewPainPoint.review_id)).desc(), PainPoint.canonical_name)
        )
        return [
            {
                "id": point.id,
                "name": point.canonical_name,
                "description": point.description,
                "reviews": review_count,
                "books": book_count,
                "severity": round(float(severity or 0), 2),
                "solvability": point.human_solvability_score if point.human_solvability_score is not None else point.system_solvability_score,
                "confidence": point.confidence,
                "solution": point.suggested_solution,
            }
            for point, review_count, book_count, severity in self.session.execute(statement)
        ]

    def pain_point_evidence(self, pain_point_id: int) -> list[dict[str, object]]:
        statement = (
            select(ReviewPainPoint, Review, Book.title)
            .join(Review, Review.id == ReviewPainPoint.review_id)
            .join(Book, Book.id == Review.book_id)
            .where(ReviewPainPoint.pain_point_id == pain_point_id)
            .order_by(ReviewPainPoint.severity.desc(), Review.id.desc())
        )
        return [
            {
                "review_id": review.id,
                "book_id": review.book_id,
                "book": book_title,
                "rating": review.rating,
                "severity": link.severity,
                "evidence": link.extraction_text,
                "review": review.raw_body,
            }
            for link, review, book_title in self.session.execute(statement)
        ]

    def praise_summaries(self, niche_id: int) -> list[dict[str, object]]:
        statement = (
            select(
                PraiseFeature,
                func.count(distinct(ReviewPraiseFeature.review_id)),
                func.count(distinct(Review.book_id)),
                func.avg(ReviewPraiseFeature.strength),
            )
            .join(ReviewPraiseFeature, ReviewPraiseFeature.praise_feature_id == PraiseFeature.id)
            .join(Review, Review.id == ReviewPraiseFeature.review_id)
            .where(PraiseFeature.niche_id == niche_id)
            .group_by(PraiseFeature.id)
            .order_by(func.count(distinct(ReviewPraiseFeature.review_id)).desc(), PraiseFeature.canonical_name)
        )
        return [
            {
                "id": feature.id,
                "name": feature.canonical_name,
                "description": feature.description,
                "reviews": review_count,
                "books": book_count,
                "strength": round(float(strength or 0), 2),
                "confidence": feature.confidence,
            }
            for feature, review_count, book_count, strength in self.session.execute(statement)
        ]

    def praise_evidence(self, praise_feature_id: int) -> list[dict[str, object]]:
        statement = (
            select(ReviewPraiseFeature, Review, Book.title)
            .join(Review, Review.id == ReviewPraiseFeature.review_id)
            .join(Book, Book.id == Review.book_id)
            .where(ReviewPraiseFeature.praise_feature_id == praise_feature_id)
            .order_by(ReviewPraiseFeature.strength.desc(), Review.id.desc())
        )
        return [
            {
                "review_id": review.id,
                "book_id": review.book_id,
                "book": book_title,
                "rating": review.rating,
                "strength": link.strength,
                "evidence": link.extraction_text,
                "review": review.raw_body,
            }
            for link, review, book_title in self.session.execute(statement)
        ]

    def analysis_runs(self, niche_id: int) -> list[dict[str, object]]:
        runs = self.session.scalars(
            select(AnalysisRun).where(AnalysisRun.niche_id == niche_id).order_by(AnalysisRun.started_at.desc())
        )
        return [
            {
                "Run": run.id,
                "Status": run.status,
                "Provider": run.provider,
                "Model": run.model,
                "Started": run.started_at,
                "Reviews": (run.result_json or {}).get("review_count"),
                "Analyzed": (run.result_json or {}).get("analyzed_count"),
                "Cached": (run.result_json or {}).get("cached_count"),
                "Input tokens": run.input_tokens,
                "Output tokens": run.output_tokens,
                "Estimated cost": run.estimated_cost_usd,
                "Error": run.error_message,
            }
            for run in runs
        ]
