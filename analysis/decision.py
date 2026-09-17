"""Evidence-backed Phase 4 component scoring and decision explanations."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import log1p
from statistics import mean, median
from typing import Any, Mapping, Sequence

from analysis.scoring import (
    COMPONENTS,
    ConfidenceInputs,
    ConfidenceTargets,
    calculate_confidence,
    calculate_overall_score,
    calculate_unmet_demand_index,
    clamp_score,
    recommendation_label,
)


@dataclass(frozen=True, slots=True)
class DecisionEvidence:
    """Observable aggregate facts used by the score model.

    Empty sequences mean the observation was not supplied. They are never filled
    with an estimated marketplace value.
    """

    book_count: int
    review_count: int
    analyzed_review_count: int
    reviewed_book_count: int
    analyzed_book_count: int
    market_review_counts: tuple[int, ...] = ()
    best_seller_ranks: tuple[int, ...] = ()
    prices: tuple[float, ...] = ()
    ratings: tuple[float, ...] = ()
    page_counts: tuple[int, ...] = ()
    publication_age_days: tuple[int, ...] = ()
    recent_review_count: int = 0
    dated_review_count: int = 0
    recent_book_count: int = 0
    dated_book_count: int = 0
    formats: tuple[str, ...] = ()
    publishers: tuple[str, ...] = ()
    solvable_pain_mentions: int = 0
    pain_book_count: int = 0
    pain_severities: tuple[float, ...] = ()
    pain_solvabilities: tuple[float, ...] = ()
    topic_count: int = 0
    outcome_count: int = 0
    pain_point_count: int = 0
    praise_feature_count: int = 0
    field_coverage: Mapping[str, float] | None = None
    collection_recency_score: float = 0
    analyzed_reviews_by_book: tuple[int, ...] = ()
    regulated_term_hits: tuple[str, ...] = ()
    expertise_term_hits: tuple[str, ...] = ()
    asset_term_hits: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DecisionTargets:
    review_traction: int = 1_500
    difficult_review_scale: int = 2_000
    maximum_rank: int = 1_000_000
    recent_review_days: int = 365
    recent_publication_days: int = 1_095
    mature_publication_days: int = 1_825
    recurring_gap_ratio: float = 0.25
    price_floor: float = 7.99
    price_target: float = 17.99
    preferred_min_pages: int = 100
    preferred_max_pages: int = 250
    target_formats: int = 2
    target_topics: int = 8
    target_outcomes: int = 6
    target_solution_angles: int = 8


@dataclass(frozen=True, slots=True)
class ComponentResult:
    score: float
    factors: Mapping[str, float]
    inputs: Mapping[str, Any]
    calculation: str
    missing: tuple[str, ...]
    explanation: str
    observed_weight: float

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class DecisionResult:
    components: Mapping[str, ComponentResult]
    automated_overall_score: float
    confidence_score: float
    confidence_parts: Mapping[str, float]
    confidence_inputs: Mapping[str, Any]
    warnings: tuple[str, ...]
    unmet_demand_index: float
    udi_factors: Mapping[str, float]
    udi_explanation: str
    recommendation: str


def _weighted_available(
    factors: Mapping[str, tuple[float | None, float]],
) -> tuple[float, dict[str, float], float]:
    available = {name: (clamp_score(value), weight) for name, (value, weight) in factors.items() if value is not None}
    observed_weight = sum(weight for _, weight in available.values())
    if observed_weight <= 0:
        return 0.0, {}, 0.0
    score = sum(value * weight for value, weight in available.values()) / observed_weight
    return clamp_score(score), {name: value for name, (value, _) in available.items()}, round(observed_weight, 2)


def _log_progress(value: float, target: float) -> float:
    if value <= 0 or target <= 0:
        return 0.0
    return clamp_score(log1p(value) / log1p(target) * 100)


def _concentration_accessibility(values: Sequence[int | float]) -> float | None:
    positive = [float(value) for value in values if value > 0]
    if not positive:
        return None
    top_share = sum(sorted(positive, reverse=True)[:3]) / sum(positive) * 100
    minimum_share = min(3 / len(positive), 1.0) * 100
    if minimum_share >= 100:
        return 50.0
    return clamp_score((100 - top_share) / (100 - minimum_share) * 100)


def _category_accessibility(values: Sequence[str]) -> float | None:
    cleaned = [value.strip().casefold() for value in values if value and value.strip()]
    if not cleaned:
        return None
    largest_share = max(cleaned.count(value) for value in set(cleaned)) / len(cleaned) * 100
    minimum_share = 100 / len(cleaned)
    if minimum_share >= 100:
        return 50.0
    return clamp_score((100 - largest_share) / (100 - minimum_share) * 100)


def _page_profile_score(value: float, targets: DecisionTargets) -> float:
    if targets.preferred_min_pages <= value <= targets.preferred_max_pages:
        return 100.0
    if value < targets.preferred_min_pages:
        return clamp_score((value - 40) / (targets.preferred_min_pages - 40) * 100)
    return clamp_score((500 - value) / (500 - targets.preferred_max_pages) * 100)


def score_components(evidence: DecisionEvidence, targets: DecisionTargets = DecisionTargets()) -> dict[str, ComponentResult]:
    median_reviews = median(evidence.market_review_counts) if evidence.market_review_counts else None
    median_rank = median(evidence.best_seller_ranks) if evidence.best_seller_ranks else None
    rank_strength = None
    if median_rank is not None:
        rank_strength = 100 - _log_progress(float(median_rank), targets.maximum_rank)
    review_recency = (
        evidence.recent_review_count / evidence.dated_review_count * 100
        if evidence.dated_review_count else None
    )
    book_activity = (
        evidence.recent_book_count / evidence.dated_book_count * 100
        if evidence.dated_book_count else None
    )
    demand_score, demand_factors, demand_weight = _weighted_available({
        "review traction": (_log_progress(float(median_reviews), targets.review_traction) if median_reviews is not None else None, 0.45),
        "rank strength": (rank_strength, 0.25),
        "review recency": (review_recency, 0.15),
        "competitor activity": (book_activity, 0.15),
    })
    demand_missing = tuple(name for name, value in {
        "competitor review counts": median_reviews,
        "best-seller ranks": median_rank,
        "dated reviews": review_recency,
        "publication dates": book_activity,
    }.items() if value is None)

    median_rating = median(evidence.ratings) if evidence.ratings else None
    median_age = median(evidence.publication_age_days) if evidence.publication_age_days else None
    competition_score, competition_factors, competition_weight = _weighted_available({
        "incumbent scale accessibility": (
            100 - _log_progress(float(median_reviews), targets.difficult_review_scale)
            if median_reviews is not None else None,
            0.30,
        ),
        "review distribution accessibility": (_concentration_accessibility(evidence.market_review_counts), 0.25),
        "rating headroom": (clamp_score((4.8 - float(median_rating)) / 0.8 * 100) if median_rating is not None else None, 0.20),
        "publication age accessibility": (clamp_score(float(median_age) / targets.mature_publication_days * 100) if median_age is not None else None, 0.15),
        "publisher diversity": (_category_accessibility(evidence.publishers), 0.10),
    })
    competition_missing = tuple(name for name, available in {
        "competitor review counts": bool(evidence.market_review_counts),
        "ratings": bool(evidence.ratings),
        "publication dates": bool(evidence.publication_age_days),
        "publishers": bool(evidence.publishers),
    }.items() if not available)

    gap_denominator = evidence.analyzed_review_count or evidence.review_count
    gap_recurrence = (
        evidence.solvable_pain_mentions / gap_denominator / targets.recurring_gap_ratio * 100
        if gap_denominator else None
    )
    cross_book_gap = (
        evidence.pain_book_count / evidence.reviewed_book_count * 100
        if evidence.reviewed_book_count else None
    )
    severity = mean(evidence.pain_severities) * 10 if evidence.pain_severities else None
    solvability = mean(evidence.pain_solvabilities) * 10 if evidence.pain_solvabilities else None
    gap_score, gap_factors, gap_weight = _weighted_available({
        "recurring solvable complaints": (gap_recurrence, 0.30),
        "cross-book prevalence": (cross_book_gap, 0.25),
        "average severity": (severity, 0.20),
        "average solvability": (solvability, 0.25),
    })
    gap_missing = tuple(name for name, value in {
        "review evidence denominator": gap_denominator or None,
        "solvable pain links": evidence.solvable_pain_mentions or None,
        "pain severity": severity,
        "pain solvability": solvability,
    }.items() if value is None)

    median_price = median(evidence.prices) if evidence.prices else None
    median_pages = median(evidence.page_counts) if evidence.page_counts else None
    price_profile = None
    if median_price is not None:
        price_profile = clamp_score((float(median_price) - targets.price_floor) / (targets.price_target - targets.price_floor) * 100)
    economics_score, economics_factors, economics_weight = _weighted_available({
        "observed price position": (price_profile, 0.55),
        "page profile fit": (_page_profile_score(float(median_pages), targets) if median_pages is not None else None, 0.30),
        "format breadth": (clamp_score(len(set(evidence.formats)) / targets.target_formats * 100) if evidence.formats else None, 0.15),
    })
    economics_missing = tuple(name for name, available in {
        "prices": bool(evidence.prices),
        "page counts": bool(evidence.page_counts),
        "formats": bool(evidence.formats),
    }.items() if not available)

    analysis_coverage = (
        evidence.analyzed_review_count / evidence.review_count * 100
        if evidence.review_count else None
    )
    structured_count = evidence.topic_count + evidence.outcome_count + evidence.pain_point_count + evidence.praise_feature_count
    structured_evidence = clamp_score(structured_count / 12 * 100) if evidence.analyzed_review_count else None
    verification_fit = clamp_score(
        100 - 40 * len(evidence.regulated_term_hits) - 20 * len(evidence.expertise_term_hits)
    )
    asset_fit = clamp_score(100 - 25 * len(evidence.asset_term_hits))
    ai_score, ai_factors, ai_weight = _weighted_available({
        "analysis coverage": (analysis_coverage, 0.30),
        "structured evidence": (structured_evidence, 0.25),
        "verification burden screen": (verification_fit, 0.30),
        "asset burden screen": (asset_fit, 0.15),
    })
    ai_missing = tuple(name for name, available in {
        "reviews": evidence.review_count > 0,
        "structured review analysis": evidence.analyzed_review_count > 0,
    }.items() if not available)

    topic_breadth = clamp_score(evidence.topic_count / targets.target_topics * 100) if evidence.analyzed_review_count else None
    outcome_breadth = clamp_score(evidence.outcome_count / targets.target_outcomes * 100) if evidence.analyzed_review_count else None
    solution_angles = clamp_score((evidence.pain_point_count + evidence.praise_feature_count) / targets.target_solution_angles * 100) if evidence.analyzed_review_count or evidence.solvable_pain_mentions else None
    expansion_score, expansion_factors, expansion_weight = _weighted_available({
        "topic breadth": (topic_breadth, 0.30),
        "desired-outcome breadth": (outcome_breadth, 0.30),
        "evidence-backed solution angles": (solution_angles, 0.25),
        "observed format breadth": (clamp_score(len(set(evidence.formats)) / 3 * 100) if evidence.formats else None, 0.15),
    })
    expansion_missing = tuple(name for name, available in {
        "structured review analysis": evidence.analyzed_review_count > 0,
        "formats": bool(evidence.formats),
    }.items() if not available)

    return {
        "demand": ComponentResult(demand_score, demand_factors, {
            "median competitor reviews": median_reviews,
            "median best-seller rank": median_rank,
            "recent dated reviews": f"{evidence.recent_review_count}/{evidence.dated_review_count}",
            "recently published books": f"{evidence.recent_book_count}/{evidence.dated_book_count}",
        }, "Weighted average of available demand signals: 45% review traction, 25% rank strength, 15% review recency, 15% competitor activity.", demand_missing, "Higher values mean stronger observed attention and current category activity; no sales are inferred.", demand_weight),
        "competition": ComponentResult(competition_score, competition_factors, {
            "median competitor reviews": median_reviews,
            "median rating": median_rating,
            "median publication age days": median_age,
            "observed publishers": len(evidence.publishers),
        }, "Weighted accessibility score from incumbent scale, review concentration, rating headroom, publication age, and publisher diversity.", competition_missing, "Higher values mean a more accessible competitive environment, not fewer competitors.", competition_weight),
        "customer_gap": ComponentResult(gap_score, gap_factors, {
            "solvable review-linked mentions": evidence.solvable_pain_mentions,
            "evidence denominator": gap_denominator,
            "books with solvable pain evidence": evidence.pain_book_count,
            "reviewed books": evidence.reviewed_book_count,
        }, "Weighted average of recurring solvable complaints (30%), cross-book prevalence (25%), severity (20%), and solvability (25%).", gap_missing, "Only review-linked pain evidence marked solvable is included; logistics and buyer mismatch are excluded upstream.", gap_weight),
        "economics": ComponentResult(economics_score, economics_factors, {
            "median observed price": median_price,
            "median observed pages": median_pages,
            "observed formats": sorted(set(evidence.formats)),
        }, "Weighted profile score from observed price position (55%), page profile (30%), and format breadth (15%).", economics_missing, "This is a production-profile screen only; it does not estimate royalty, print cost, or profit.", economics_weight),
        "ai_suitability": ComponentResult(ai_score, ai_factors, {
            "analyzed reviews": f"{evidence.analyzed_review_count}/{evidence.review_count}",
            "structured evidence groups": structured_count,
            "regulated term hits": list(evidence.regulated_term_hits),
            "expertise term hits": list(evidence.expertise_term_hits),
            "asset term hits": list(evidence.asset_term_hits),
        }, "Weighted screen from analysis coverage (30%), structured evidence (25%), verification burden (30%), and asset burden (15%).", ai_missing, "This is a planning screen. Keyword checks do not replace expert review, fact checking, or rights clearance.", ai_weight),
        "expansion": ComponentResult(expansion_score, expansion_factors, {
            "distinct topics": evidence.topic_count,
            "distinct desired outcomes": evidence.outcome_count,
            "pain and praise groups": evidence.pain_point_count + evidence.praise_feature_count,
            "observed formats": sorted(set(evidence.formats)),
        }, "Weighted breadth score from topics (30%), outcomes (30%), solution angles (25%), and observed formats (15%).", expansion_missing, "Higher values indicate more evidence-backed directions to validate; they are not generated product claims.", expansion_weight),
    }


def _evidence_distribution(values: Sequence[int]) -> tuple[float, float | None]:
    positive = [value for value in values if value > 0]
    if not positive:
        return 0.0, None
    total = sum(positive)
    shares = [value / total for value in positive]
    maximum_share = max(shares)
    if len(shares) == 1:
        return 0.0, maximum_share
    hhi = sum(share * share for share in shares)
    minimum_hhi = 1 / len(shares)
    evenness = 1 - (hhi - minimum_hhi) / (1 - minimum_hhi)
    return clamp_score(evenness * 100) / 100, maximum_share


def build_decision(
    evidence: DecisionEvidence,
    weights: Mapping[str, float],
    *,
    targets: DecisionTargets = DecisionTargets(),
    confidence_targets: ConfidenceTargets = ConfidenceTargets(),
) -> DecisionResult:
    components = score_components(evidence, targets)
    component_scores = {name: result.score for name, result in components.items()}
    overall = calculate_overall_score(component_scores, weights)
    field_coverage = dict(evidence.field_coverage or {})
    field_completeness = mean(field_coverage.values()) if field_coverage else 0.0
    analysis_completeness = (
        evidence.analyzed_review_count / evidence.review_count
        if evidence.review_count else 0.0
    )
    distribution, maximum_evidence_share = _evidence_distribution(evidence.analyzed_reviews_by_book)
    confidence_inputs = ConfidenceInputs(
        book_count=evidence.book_count,
        review_count=evidence.review_count,
        reviewed_book_count=evidence.reviewed_book_count,
        field_completeness=field_completeness,
        analysis_completeness=analysis_completeness,
        recency_score=evidence.collection_recency_score,
        evidence_distribution=distribution,
    )
    confidence, confidence_parts = calculate_confidence(confidence_inputs, confidence_targets)
    warnings: list[str] = []
    if evidence.book_count < confidence_targets.target_books:
        warnings.append(f"Competitor coverage is {evidence.book_count}/{confidence_targets.target_books} books.")
    if evidence.review_count < confidence_targets.target_reviews:
        warnings.append(f"Review coverage is {evidence.review_count}/{confidence_targets.target_reviews} reviews.")
    reviewed_ratio = evidence.reviewed_book_count / evidence.book_count if evidence.book_count else 0
    if reviewed_ratio < confidence_targets.target_cross_book_coverage:
        warnings.append(f"Reviews cover {evidence.reviewed_book_count}/{evidence.book_count} competitor books.")
    for field, coverage in sorted(field_coverage.items()):
        if coverage < confidence_targets.target_field_completeness:
            warnings.append(f"{field.replace('_', ' ').title()} is present for {coverage:.0%} of competitor books.")
    if analysis_completeness < confidence_targets.target_analysis_completeness:
        warnings.append(f"Structured analysis covers {evidence.analyzed_review_count}/{evidence.review_count} reviews.")
    if maximum_evidence_share is not None and maximum_evidence_share > confidence_targets.maximum_single_book_share:
        warnings.append(f"One book supplies {maximum_evidence_share:.0%} of analyzed review evidence.")
    if evidence.collection_recency_score < confidence_targets.target_recency_score:
        warnings.append("The latest collected market observation is outside the preferred recency window.")
    if not evidence.solvable_pain_mentions:
        warnings.append("No solvable, review-linked customer pain evidence is available.")

    solvability_factor = mean(evidence.pain_solvabilities) * 10 if evidence.pain_solvabilities else 0.0
    udi_factors = {
        "demand strength": components["demand"].score,
        "gap strength": components["customer_gap"].score,
        "solvability": clamp_score(solvability_factor),
        "competitive accessibility": components["competition"].score,
    }
    udi = calculate_unmet_demand_index(*udi_factors.values())
    recommendation = recommendation_label(overall, confidence)
    return DecisionResult(
        components=components,
        automated_overall_score=overall,
        confidence_score=confidence,
        confidence_parts=confidence_parts,
        confidence_inputs=asdict(confidence_inputs),
        warnings=tuple(warnings),
        unmet_demand_index=udi,
        udi_factors=udi_factors,
        udi_explanation="UDI multiplies demand, customer-gap strength, average solvability, and competitive accessibility. A weak factor therefore constrains the diagnostic.",
        recommendation=recommendation,
    )


def validate_weights(weights: Mapping[str, float]) -> None:
    missing = set(COMPONENTS) - set(weights)
    if missing:
        raise ValueError(f"Missing score weights: {', '.join(sorted(missing))}")
    if any(float(weights[name]) < 0 for name in COMPONENTS):
        raise ValueError("Scoring weights cannot be negative")
    if abs(sum(float(weights[name]) for name in COMPONENTS) - 1.0) > 1e-9:
        raise ValueError("Scoring weights must total 1.0")
