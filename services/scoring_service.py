"""Transactions for calculating scores and recording human decision overrides."""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timezone
from pathlib import Path
import re
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from analysis.decision import DecisionEvidence, DecisionTargets, build_decision
from analysis.scoring import ConfidenceTargets, load_weights
from config.settings import get_settings
from models import (
    Book,
    Niche,
    PainPoint,
    PraiseFeature,
    Review,
    ReviewAnalysis,
    ReviewPainPoint,
    ScoreSnapshot,
)


REGULATED_TERMS = ("medical", "medicine", "legal", "law", "tax", "financial", "investing", "therapy")
EXPERTISE_TERMS = ("certification", "engineering", "structural", "diagnosis", "treatment", "compliance")
ASSET_TERMS = ("photography", "photo", "illustration", "diagram", "map", "workbook")


def _age_days(value: date | datetime, today: date) -> int:
    observed = value.date() if isinstance(value, datetime) else value
    return max(0, (today - observed).days)


def _load_policy(path: Path) -> tuple[str, DecisionTargets, ConfidenceTargets, dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    decision_payload = payload.get("component_targets", {})
    confidence_payload = payload.get("confidence", {})
    decision_targets = DecisionTargets(**{
        key: decision_payload[key]
        for key in DecisionTargets.__dataclass_fields__
        if key in decision_payload
    })
    confidence_targets = ConfidenceTargets(**{
        key: confidence_payload[key]
        for key in ConfidenceTargets.__dataclass_fields__
        if key in confidence_payload
    })
    return str(payload.get("version", "2")), decision_targets, confidence_targets, payload


def collect_decision_evidence(
    session: Session,
    niche_id: int,
    *,
    today: date | None = None,
    targets: DecisionTargets = DecisionTargets(),
) -> DecisionEvidence:
    niche = session.get(Niche, niche_id)
    if niche is None:
        raise ValueError("Niche not found")
    today = today or datetime.now(timezone.utc).date()
    books = list(session.scalars(select(Book).where(Book.niche_id == niche_id)))
    book_ids = [book.id for book in books]
    reviews = list(session.scalars(
        select(Review).where(Review.book_id.in_(book_ids)) if book_ids else select(Review).where(False)
    ))
    review_ids = [review.id for review in reviews]
    analyses = list(session.scalars(
        select(ReviewAnalysis).where(ReviewAnalysis.review_id.in_(review_ids))
        if review_ids else select(ReviewAnalysis).where(False)
    ))
    analysis_review_ids = {analysis.review_id for analysis in analyses}
    review_by_id = {review.id: review for review in reviews}

    pain_rows = list(session.execute(
        select(ReviewPainPoint, PainPoint)
        .join(PainPoint, PainPoint.id == ReviewPainPoint.pain_point_id)
        .where(
            ReviewPainPoint.review_id.in_(review_ids),
            ReviewPainPoint.solvable.is_(True),
            PainPoint.niche_id == niche_id,
        )
    )) if review_ids else []
    pain_book_ids = {review_by_id[link.review_id].book_id for link, _ in pain_rows}
    pain_solvabilities = tuple(
        float(value)
        for _, point in pain_rows
        if (value := point.human_solvability_score if point.human_solvability_score is not None else point.system_solvability_score) is not None
    )

    topics = {topic.strip().casefold() for analysis in analyses for topic in (analysis.topics_json or []) if topic.strip()}
    outcomes = {outcome.strip().casefold() for analysis in analyses for outcome in (analysis.desired_outcomes_json or []) if outcome.strip()}
    analyzed_book_counts: dict[int, int] = {}
    for review_id in analysis_review_ids:
        book_id = review_by_id[review_id].book_id
        analyzed_book_counts[book_id] = analyzed_book_counts.get(book_id, 0) + 1

    field_names = ("price", "rating", "review_count", "best_seller_rank", "page_count", "publication_date", "publisher", "format")
    field_coverage = {
        field: (sum(getattr(book, field) is not None for book in books) / len(books) if books else 0.0)
        for field in field_names
    }
    collected_ages = [_age_days(book.date_collected, today) for book in books if book.date_collected]
    recency_score = max(0.0, 100 - min(collected_ages, default=365) / 365 * 100) if collected_ages else 0.0
    searchable_text = " ".join(filter(None, [niche.name, niche.seed_keyword, niche.description or "", *topics, *outcomes])).casefold()
    searchable_terms = set(re.findall(r"[a-z]+", searchable_text))

    reviewed_book_ids = {review.book_id for review in reviews}
    dated_reviews = [review for review in reviews if review.review_date]
    dated_books = [book for book in books if book.publication_date]
    return DecisionEvidence(
        book_count=len(books),
        review_count=len(reviews),
        analyzed_review_count=len(analyses),
        reviewed_book_count=len(reviewed_book_ids),
        analyzed_book_count=len(analyzed_book_counts),
        market_review_counts=tuple(int(book.review_count) for book in books if book.review_count is not None and book.review_count >= 0),
        best_seller_ranks=tuple(int(book.best_seller_rank) for book in books if book.best_seller_rank is not None and book.best_seller_rank > 0),
        prices=tuple(float(book.price) for book in books if book.price is not None and book.price >= 0),
        ratings=tuple(float(book.rating) for book in books if book.rating is not None),
        page_counts=tuple(int(book.page_count) for book in books if book.page_count is not None and book.page_count > 0),
        publication_age_days=tuple(_age_days(book.publication_date, today) for book in dated_books),
        recent_review_count=sum(_age_days(review.review_date, today) <= targets.recent_review_days for review in dated_reviews),
        dated_review_count=len(dated_reviews),
        recent_book_count=sum(_age_days(book.publication_date, today) <= targets.recent_publication_days for book in dated_books),
        dated_book_count=len(dated_books),
        formats=tuple(book.format for book in books if book.format),
        publishers=tuple(book.publisher for book in books if book.publisher),
        solvable_pain_mentions=len(pain_rows),
        pain_book_count=len(pain_book_ids),
        pain_severities=tuple(float(link.severity) for link, _ in pain_rows),
        pain_solvabilities=pain_solvabilities,
        topic_count=len(topics),
        outcome_count=len(outcomes),
        pain_point_count=len({point.id for _, point in pain_rows}),
        praise_feature_count=len(list(session.scalars(
            select(PraiseFeature.id).where(PraiseFeature.niche_id == niche_id)
        ))),
        field_coverage=field_coverage,
        collection_recency_score=recency_score,
        analyzed_reviews_by_book=tuple(analyzed_book_counts.values()),
        regulated_term_hits=tuple(term for term in REGULATED_TERMS if term in searchable_terms),
        expertise_term_hits=tuple(term for term in EXPERTISE_TERMS if term in searchable_terms),
        asset_term_hits=tuple(term for term in ASSET_TERMS if term in searchable_terms),
    )


def calculate_niche_score(
    session: Session,
    niche_id: int,
    *,
    config_path: Path | None = None,
    today: date | None = None,
) -> ScoreSnapshot:
    path = config_path or get_settings().scoring_config_path
    weights = load_weights(path)
    version, targets, confidence_targets, policy = _load_policy(path)
    evidence = collect_decision_evidence(session, niche_id, today=today, targets=targets)
    result = build_decision(evidence, weights, targets=targets, confidence_targets=confidence_targets)
    snapshot = ScoreSnapshot(
        niche_id=niche_id,
        scoring_version=version,
        demand_score=result.components["demand"].score,
        competition_score=result.components["competition"].score,
        customer_gap_score=result.components["customer_gap"].score,
        economics_score=result.components["economics"].score,
        ai_suitability_score=result.components["ai_suitability"].score,
        expansion_score=result.components["expansion"].score,
        automated_overall_score=result.automated_overall_score,
        human_overall_score=None,
        confidence_score=result.confidence_score,
        unmet_demand_index=result.unmet_demand_index,
        weights_json=dict(weights),
        explanation_json={
            "components": {name: component.as_dict() for name, component in result.components.items()},
            "confidence": {
                "parts": dict(result.confidence_parts),
                "inputs": dict(result.confidence_inputs),
                "warnings": list(result.warnings),
            },
            "udi": {
                "factors": dict(result.udi_factors),
                "explanation": result.udi_explanation,
            },
            "recommendation": result.recommendation,
            "policy": policy,
            "human_override": None,
        },
    )
    session.add(snapshot)
    session.flush()
    return snapshot


def apply_human_score_override(
    session: Session,
    *,
    niche_id: int,
    human_score: float,
    rationale: str,
) -> ScoreSnapshot:
    if not 0 <= human_score <= 100:
        raise ValueError("Human score must be between 0 and 100")
    if not rationale.strip():
        raise ValueError("A rationale is required for a human score override")
    latest = session.scalar(
        select(ScoreSnapshot)
        .where(ScoreSnapshot.niche_id == niche_id)
        .order_by(ScoreSnapshot.calculated_at.desc(), ScoreSnapshot.id.desc())
        .limit(1)
    )
    if latest is None:
        raise ValueError("Calculate an automated score before adding a human override")
    explanation = deepcopy(latest.explanation_json)
    explanation["human_override"] = {
        "score": round(float(human_score), 2),
        "rationale": rationale.strip(),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "automated_score_preserved": latest.automated_overall_score,
    }
    snapshot = ScoreSnapshot(
        niche_id=niche_id,
        scoring_version=latest.scoring_version,
        demand_score=latest.demand_score,
        competition_score=latest.competition_score,
        customer_gap_score=latest.customer_gap_score,
        economics_score=latest.economics_score,
        ai_suitability_score=latest.ai_suitability_score,
        expansion_score=latest.expansion_score,
        automated_overall_score=latest.automated_overall_score,
        human_overall_score=round(float(human_score), 2),
        confidence_score=latest.confidence_score,
        unmet_demand_index=latest.unmet_demand_index,
        weights_json=deepcopy(latest.weights_json),
        explanation_json=explanation,
    )
    session.add(snapshot)
    session.flush()
    return snapshot
