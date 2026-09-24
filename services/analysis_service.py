"""Transactional, cache-aware orchestration for review evidence extraction."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from config.settings import Settings, get_settings
from llm.base import LLMProvider, ProviderContractError, ProviderUsage
from llm.factory import build_provider
from llm.schemas import (
    PROMPT_VERSION,
    SCHEMA_VERSION,
    ComplaintCategory,
    PainPointExtraction,
    PraiseExtraction,
    ReviewExtraction,
    ReviewForAnalysis,
)
from models import AnalysisRun, Book, PainPoint, PraiseFeature, Review, ReviewAnalysis, ReviewPainPoint, ReviewPraiseFeature


ProgressCallback = Callable[[int, int, str], None]
EXCLUDED_CATEGORIES = {
    ComplaintCategory.SHIPPING,
    ComplaintCategory.SELLER,
    ComplaintCategory.BUYER_MISMATCH,
}


@dataclass(frozen=True, slots=True)
class AnalysisSummary:
    run_id: int
    review_count: int
    analyzed_count: int
    cached_count: int
    pain_point_count: int
    praise_feature_count: int
    excluded_complaint_count: int
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float | None


def _cache_key(review: Review, provider: LLMProvider) -> str:
    source = "|".join((review.normalized_hash, provider.name, provider.model, SCHEMA_VERSION, PROMPT_VERSION))
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def _validate_batch(expected_ids: list[int], results: list[ReviewExtraction]) -> None:
    actual_ids = [result.review_id for result in results]
    if len(actual_ids) != len(set(actual_ids)) or set(actual_ids) != set(expected_ids):
        raise ProviderContractError(
            f"Provider returned review IDs {actual_ids}; expected exactly {expected_ids}."
        )


def _validate_clusters(candidate_names: set[str], clusters: list[object]) -> None:
    members = [name for cluster in clusters for name in cluster.member_names]  # type: ignore[attr-defined]
    if len(members) != len(set(members)) or set(members) != candidate_names:
        raise ProviderContractError("Every extracted candidate must appear in exactly one cluster.")


def _cost(usage: ProviderUsage, provider: LLMProvider, settings: Settings) -> float | None:
    if provider.name != "openai":
        return None
    if settings.openai_input_cost_per_million <= 0 and settings.openai_output_cost_per_million <= 0:
        return None
    return round(
        usage.input_tokens / 1_000_000 * settings.openai_input_cost_per_million
        + usage.output_tokens / 1_000_000 * settings.openai_output_cost_per_million,
        6,
    )


def analyze_niche_reviews(
    session: Session,
    *,
    niche_id: int,
    provider: LLMProvider | None = None,
    provider_name: str | None = None,
    batch_size: int | None = None,
    force: bool = False,
    progress: ProgressCallback | None = None,
    settings: Settings | None = None,
) -> AnalysisSummary:
    """Analyze all reviews in a niche and replace derived links only on success."""
    settings = settings or get_settings()
    provider = provider or build_provider(provider_name, settings)
    size = max(1, min(50, batch_size or settings.llm_batch_size))
    reviews = list(session.scalars(
        select(Review).join(Book, Book.id == Review.book_id).where(Book.niche_id == niche_id).order_by(Review.id)
    ))
    if not reviews:
        raise ValueError("This niche has no reviews to analyze.")

    run = AnalysisRun(
        niche_id=niche_id,
        analysis_type="review_evidence",
        provider=provider.name,
        model=provider.model,
        prompt_version=PROMPT_VERSION,
        parameters_json={"batch_size": size, "force": force, "schema_version": SCHEMA_VERSION},
        status="running",
    )
    session.add(run)
    session.commit()
    run_id = run.id

    try:
        existing = {
            item.review_id: item
            for item in session.scalars(
                select(ReviewAnalysis).where(ReviewAnalysis.review_id.in_([review.id for review in reviews]))
            )
        }
        extracted: dict[int, ReviewExtraction] = {}
        pending: list[Review] = []
        usage = ProviderUsage()
        for review in reviews:
            cached = existing.get(review.id)
            if not force and cached and cached.content_hash == _cache_key(review, provider):
                extracted[review.id] = ReviewExtraction.model_validate(cached.result_json)
            else:
                pending.append(review)

        total = len(reviews)
        completed = len(extracted)
        if progress:
            progress(completed, total, f"Reused {completed} cached reviews")

        if not pending:
            excluded_count = sum(
                1
                for result in extracted.values()
                for item in result.pain_points
                if item.category in EXCLUDED_CATEGORIES or not item.solvable_in_book
            )
            active_pain_point_count = session.scalar(
                select(func.count(func.distinct(ReviewPainPoint.pain_point_id)))
                .join(Review, Review.id == ReviewPainPoint.review_id)
                .join(Book, Book.id == Review.book_id)
                .where(Book.niche_id == niche_id)
            ) or 0
            active_praise_feature_count = session.scalar(
                select(func.count(func.distinct(ReviewPraiseFeature.praise_feature_id)))
                .join(Review, Review.id == ReviewPraiseFeature.review_id)
                .join(Book, Book.id == Review.book_id)
                .where(Book.niche_id == niche_id)
            ) or 0
            estimated_cost = _cost(usage, provider, settings)
            run = session.get(AnalysisRun, run_id)
            assert run is not None
            run.status = "completed"
            run.completed_at = datetime.now(timezone.utc)
            run.input_tokens = 0
            run.output_tokens = 0
            run.estimated_cost_usd = estimated_cost
            run.result_json = {
                "reviews": [extracted[review.id].model_dump(mode="json") for review in reviews],
                "review_count": total,
                "analyzed_count": 0,
                "cached_count": total,
                "pain_point_count": active_pain_point_count,
                "praise_feature_count": active_praise_feature_count,
                "excluded_complaint_count": excluded_count,
            }
            session.commit()
            if progress:
                progress(total, total, "All review evidence was current; provider calls skipped")
            return AnalysisSummary(
                run_id=run_id,
                review_count=total,
                analyzed_count=0,
                cached_count=total,
                pain_point_count=active_pain_point_count,
                praise_feature_count=active_praise_feature_count,
                excluded_complaint_count=excluded_count,
                input_tokens=0,
                output_tokens=0,
                estimated_cost_usd=estimated_cost,
            )

        for offset in range(0, len(pending), size):
            batch = pending[offset : offset + size]
            request = [
                ReviewForAnalysis(review_id=review.id, rating=review.rating, title=review.title, body=review.normalized_body)
                for review in batch
            ]
            response = provider.analyze_reviews(request)
            _validate_batch([review.id for review in batch], response.payload.reviews)
            extracted.update({item.review_id: item for item in response.payload.reviews})
            usage += response.usage
            completed += len(batch)
            if progress:
                progress(completed, total, f"Analyzed {completed} of {total} reviews")

        pain_candidates = [
            item for result in extracted.values() for item in result.pain_points
            if item.category not in EXCLUDED_CATEGORIES and item.solvable_in_book
        ]
        praise_candidates = [item for result in extracted.values() for item in result.praise]
        unique_pain = list({item.name: item for item in pain_candidates}.values())
        unique_praise = list({item.name: item for item in praise_candidates}.values())
        pain_clusters = []
        praise_clusters = []
        if unique_pain:
            response = provider.cluster_pain_points(unique_pain)
            pain_clusters = response.payload.clusters
            usage += response.usage
            _validate_clusters({item.name for item in unique_pain}, pain_clusters)
        if unique_praise:
            response = provider.cluster_praise_features(unique_praise)
            praise_clusters = response.payload.clusters
            usage += response.usage
            _validate_clusters({item.name for item in unique_praise}, praise_clusters)

        review_ids = [review.id for review in reviews]
        prior_system_targets: dict[str, int] = {}
        prior_links = session.execute(
            select(ReviewPainPoint, PainPoint)
            .join(PainPoint, PainPoint.id == ReviewPainPoint.pain_point_id)
            .where(ReviewPainPoint.review_id.in_(review_ids))
        )
        for link, point in prior_links:
            data = link.extraction_json or {}
            prior_system_targets[str(data.get("system_cluster_name") or point.canonical_name)] = point.id

        session.execute(delete(ReviewPainPoint).where(ReviewPainPoint.review_id.in_(review_ids)))
        session.execute(delete(ReviewPraiseFeature).where(ReviewPraiseFeature.review_id.in_(review_ids)))

        pain_member_map = {member: cluster for cluster in pain_clusters for member in cluster.member_names}
        praise_member_map = {member: cluster for cluster in praise_clusters for member in cluster.member_names}
        pain_entities: dict[str, PainPoint] = {}
        for cluster in pain_clusters:
            point = session.get(PainPoint, prior_system_targets.get(cluster.canonical_name, -1))
            if point is None:
                point = session.scalar(select(PainPoint).where(
                    PainPoint.niche_id == niche_id, PainPoint.canonical_name == cluster.canonical_name
                ))
            if point is None:
                point = PainPoint(niche_id=niche_id, canonical_name=cluster.canonical_name, description=cluster.description)
                session.add(point)
                session.flush()
            elif point.canonical_name == cluster.canonical_name:
                point.description = cluster.description
            point.suggested_solution = cluster.suggested_solution
            pain_entities[cluster.canonical_name] = point

        praise_entities: dict[str, PraiseFeature] = {}
        for cluster in praise_clusters:
            feature = session.scalar(select(PraiseFeature).where(
                PraiseFeature.niche_id == niche_id, PraiseFeature.canonical_name == cluster.canonical_name
            ))
            if feature is None:
                feature = PraiseFeature(niche_id=niche_id, canonical_name=cluster.canonical_name, description=cluster.description)
                session.add(feature)
                session.flush()
            else:
                feature.description = cluster.description
            praise_entities[cluster.canonical_name] = feature

        point_stats: dict[int, list[PainPointExtraction]] = defaultdict(list)
        praise_stats: dict[int, list[PraiseExtraction]] = defaultdict(list)
        pain_links: dict[tuple[int, int], ReviewPainPoint] = {}
        praise_links: dict[tuple[int, int], ReviewPraiseFeature] = {}
        excluded_count = 0
        for review in reviews:
            result = extracted[review.id]
            current = existing.get(review.id)
            values = {
                "analysis_run_id": run_id,
                "sentiment": result.sentiment.value,
                "topics_json": result.topics,
                "features_json": result.features,
                "desired_outcomes_json": result.desired_outcomes,
                "reader_skill_level": result.reader_skill_level.value,
                "purchase_motivation": result.purchase_motivation,
                "result_json": result.model_dump(mode="json"),
                "schema_version": SCHEMA_VERSION,
                "content_hash": _cache_key(review, provider),
                "analyzed_at": datetime.now(timezone.utc),
            }
            if current is None:
                current = ReviewAnalysis(review_id=review.id, **values)
                session.add(current)
            else:
                for key, value in values.items():
                    setattr(current, key, value)
            for candidate in result.pain_points:
                if candidate.category in EXCLUDED_CATEGORIES or not candidate.solvable_in_book:
                    excluded_count += 1
                    continue
                cluster = pain_member_map[candidate.name]
                point = pain_entities[cluster.canonical_name]
                key = (review.id, point.id)
                point_stats[point.id].append(candidate)
                if key not in pain_links:
                    pain_links[key] = ReviewPainPoint(
                        review_id=review.id, pain_point_id=point.id, severity=candidate.severity,
                        solvable=True, extraction_text=candidate.evidence_text,
                        extraction_json={**candidate.model_dump(mode="json"), "system_cluster_name": cluster.canonical_name},
                    )
                else:
                    pain_links[key].severity = max(pain_links[key].severity, candidate.severity)
            for candidate in result.praise:
                cluster = praise_member_map[candidate.name]
                feature = praise_entities[cluster.canonical_name]
                key = (review.id, feature.id)
                praise_stats[feature.id].append(candidate)
                if key not in praise_links:
                    praise_links[key] = ReviewPraiseFeature(
                        review_id=review.id, praise_feature_id=feature.id,
                        strength=candidate.strength, extraction_text=candidate.evidence_text,
                    )
                else:
                    praise_links[key].strength = max(praise_links[key].strength, candidate.strength)
        session.add_all([*pain_links.values(), *praise_links.values()])

        for point in pain_entities.values():
            candidates = point_stats[point.id]
            point.system_solvability_score = sum(item.solvability_score for item in candidates) / len(candidates)
            point.confidence = sum(extracted[review_id].confidence for review_id, point_id in pain_links if point_id == point.id) / len({review_id for review_id, point_id in pain_links if point_id == point.id})
        for feature in praise_entities.values():
            candidates = praise_stats[feature.id]
            feature.confidence = sum(item.strength for item in candidates) / (10 * len(candidates))

        active_pain_point_count = len({point.id for point in pain_entities.values()})
        active_praise_feature_count = len({feature.id for feature in praise_entities.values()})
        estimated_cost = _cost(usage, provider, settings)
        run = session.get(AnalysisRun, run_id)
        assert run is not None
        run.status = "completed"
        run.completed_at = datetime.now(timezone.utc)
        run.input_tokens = usage.input_tokens
        run.output_tokens = usage.output_tokens
        run.estimated_cost_usd = estimated_cost
        run.result_json = {
            "reviews": [extracted[review.id].model_dump(mode="json") for review in reviews],
            "review_count": total,
            "analyzed_count": len(pending),
            "cached_count": total - len(pending),
            "pain_point_count": active_pain_point_count,
            "praise_feature_count": active_praise_feature_count,
            "excluded_complaint_count": excluded_count,
        }
        session.commit()
        return AnalysisSummary(
            run_id=run_id, review_count=total, analyzed_count=len(pending), cached_count=total - len(pending),
            pain_point_count=active_pain_point_count, praise_feature_count=active_praise_feature_count,
            excluded_complaint_count=excluded_count, input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens, estimated_cost_usd=estimated_cost,
        )
    except Exception as exc:
        session.rollback()
        failed = session.get(AnalysisRun, run_id)
        if failed is not None:
            failed.status = "failed"
            failed.completed_at = datetime.now(timezone.utc)
            failed.error_message = str(exc)[:2000]
            session.commit()
        raise
