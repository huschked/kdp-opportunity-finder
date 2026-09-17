"""Deterministic, evidence-linked Markdown opportunity reports."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median
import re
from typing import Any, Iterable

from sqlalchemy.orm import Session

from analysis.scoring import recommendation_label
from db.repositories import BookRepository, EvidenceRepository, NicheRepository, ReviewRepository, ScoreRepository


COMPONENT_LABELS = {
    "demand": "Demand",
    "competition": "Competitive opportunity",
    "customer_gap": "Customer gap",
    "economics": "Economics",
    "ai_suitability": "AI suitability",
    "expansion": "Expansion",
}


@dataclass(frozen=True, slots=True)
class OpportunityReport:
    niche_id: int
    snapshot_id: int
    file_name: str
    markdown: str
    warnings: tuple[str, ...]
    cited_review_ids: tuple[int, ...]


def _markdown_text(value: object, *, limit: int | None = None) -> str:
    text = " ".join(str(value or "").split())
    if limit and len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return re.sub(r"([\\`*_[\]<>#|])", r"\\\1", text)


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return slug or "niche"


def _ref(prefix: str, identifier: int) -> str:
    return f"[{prefix}{identifier}](#evidence-{prefix.casefold()}{identifier})"


def _number(value: object, *, decimals: int = 1, missing: str = "Missing") -> str:
    if value is None:
        return missing
    return f"{float(value):,.{decimals}f}"


def _currency(value: object) -> str:
    return f"${_number(value, decimals=2)}" if value is not None else "Missing"


def _market_summary(rows: list[dict[str, object]]) -> dict[str, float | int | None]:
    def values(name: str) -> list[float]:
        return [float(row[name]) for row in rows if row.get(name) is not None]

    review_counts = values("review_count")
    return {
        "books": len(rows),
        "median_price": median(values("price")) if values("price") else None,
        "median_rating": median(values("rating")) if values("rating") else None,
        "median_reviews": median(review_counts) if review_counts else None,
        "top_three_review_share": (
            sum(sorted(review_counts, reverse=True)[:3]) / sum(review_counts) * 100
            if review_counts and sum(review_counts) else None
        ),
    }


def _component_missing(components: dict[str, Any]) -> list[tuple[str, str]]:
    missing: list[tuple[str, str]] = []
    for key, label in COMPONENT_LABELS.items():
        for field in components.get(key, {}).get("missing", []):
            missing.append((label, str(field)))
    return missing


def _book_refs(rows: Iterable[dict[str, object]]) -> str:
    return ", ".join(_ref("B", int(row["id"])) for row in rows)


def generate_opportunity_report(
    session: Session,
    *,
    niche_id: int,
    snapshot_id: int | None = None,
    evidence_per_group: int = 3,
) -> OpportunityReport:
    niche = NicheRepository(session).get(niche_id)
    if niche is None:
        raise ValueError("Niche not found")
    scores = ScoreRepository(session)
    snapshot = scores.get(snapshot_id) if snapshot_id is not None else scores.latest_for_niche(niche_id)
    if snapshot is None or snapshot.niche_id != niche_id:
        raise ValueError("Calculate a score snapshot before generating a report")
    explanation = snapshot.explanation_json or {}
    components = explanation.get("components")
    if not isinstance(components, dict) or not components:
        raise ValueError("Recalculate this niche with the current scoring version before generating a report")

    book_rows = BookRepository(session).rows_by_niche(niche_id)
    evidence_repository = EvidenceRepository(session)
    pain_rows = evidence_repository.pain_point_summaries(niche_id)
    praise_rows = evidence_repository.praise_summaries(niche_id)
    confidence = explanation.get("confidence", {})
    warnings = [str(item) for item in confidence.get("warnings", [])]
    snapshot_inputs = confidence.get("inputs", {})
    current_review_count = ReviewRepository(session).count_by_niche(niche_id)
    current_analysis_count = ReviewRepository(session).analysis_count_by_niche(niche_id)
    stored_book_count = snapshot_inputs.get("book_count")
    stored_review_count = snapshot_inputs.get("review_count")
    if stored_book_count is not None and int(stored_book_count) != len(book_rows):
        warnings.append(
            f"The corpus now has {len(book_rows)} books, but score snapshot S{snapshot.id} used {int(stored_book_count)}. Recalculate before making a decision."
        )
    if stored_review_count is not None and int(stored_review_count) != current_review_count:
        warnings.append(
            f"The corpus now has {current_review_count} reviews, but score snapshot S{snapshot.id} used {int(stored_review_count)}. Recalculate before making a decision."
        )
    stored_analysis_ratio = snapshot_inputs.get("analysis_completeness")
    if stored_analysis_ratio is not None and stored_review_count is not None:
        stored_analysis_count = round(float(stored_analysis_ratio) * int(stored_review_count))
        if stored_analysis_count != current_analysis_count:
            warnings.append(
                f"The corpus now has {current_analysis_count} analyzed reviews, but score snapshot S{snapshot.id} used {stored_analysis_count}. Recalculate before making a decision."
            )

    effective_score = snapshot.human_overall_score if snapshot.human_overall_score is not None else snapshot.automated_overall_score
    decision_label = recommendation_label(effective_score, snapshot.confidence_score)
    snapshot_ref = _ref("S", snapshot.id)
    market = _market_summary(book_rows)
    sorted_books = sorted(book_rows, key=lambda row: (row.get("review_count") is None, -(int(row.get("review_count") or 0)), str(row.get("title"))))
    lines: list[str] = [
        f"# Opportunity report: {_markdown_text(niche.name)}",
        "",
        "> Decision-support report only. It does not predict sales or make an automatic publish decision.",
        "",
        f"Generated from score snapshot {snapshot_ref}, scoring version `{_markdown_text(snapshot.scoring_version)}`.",
        "",
        "## Decision summary",
        "",
        "| Measure | Result | Evidence |",
        "|---|---:|---|",
        f"| Decision score | {effective_score:.1f}/100 | {snapshot_ref} |",
        f"| Automated score | {snapshot.automated_overall_score:.1f}/100 | {snapshot_ref} |",
        f"| Human-adjusted score | {_number(snapshot.human_overall_score) if snapshot.human_overall_score is not None else 'Not applied'} | {snapshot_ref} |",
        f"| Confidence | {snapshot.confidence_score:.1f}/100 | {snapshot_ref} |",
        f"| Unmet Demand Index | {_number(snapshot.unmet_demand_index)}/100 | {snapshot_ref} |",
        f"| Recommendation | **{_markdown_text(decision_label)}** | {snapshot_ref} |",
        "",
    ]
    if snapshot.human_overall_score is not None:
        override = explanation.get("human_override") or {}
        lines.extend([
            f"Human adjustment rationale: {_markdown_text(override.get('rationale', 'No rationale stored.'))} {snapshot_ref}",
            "",
        ])

    lines.extend(["## Evidence health", ""])
    if warnings:
        lines.append("### Warnings")
        lines.append("")
        lines.extend(f"- {_markdown_text(warning)} {snapshot_ref}" for warning in warnings)
    else:
        lines.append(f"No confidence warnings were recorded in {snapshot_ref}.")
    missing = _component_missing(components)
    lines.extend(["", "### Missing observations", ""])
    if missing:
        lines.extend(f"- **{_markdown_text(component)}:** {_markdown_text(field)} {snapshot_ref}" for component, field in missing)
    else:
        lines.append(f"No component-level observations were marked missing in {snapshot_ref}.")

    lines.extend([
        "",
        "## Score breakdown",
        "",
        "| Component | Score | Weight | Observed factor weight | Snapshot evidence |",
        "|---|---:|---:|---:|---|",
    ])
    for key, label in COMPONENT_LABELS.items():
        component = components[key]
        lines.append(
            f"| {_markdown_text(label)} | {float(component['score']):.1f} | {float(snapshot.weights_json[key]):.0%} | "
            f"{float(component.get('observed_weight', 0)):.0%} | {snapshot_ref} → `components.{key}` |"
        )
    lines.extend(["", "### Component explanations", ""])
    for key, label in COMPONENT_LABELS.items():
        component = components[key]
        lines.extend([
            f"#### {_markdown_text(label)} — {float(component['score']):.1f}/100 {snapshot_ref}",
            "",
            _markdown_text(component.get("explanation", "")),
            "",
            f"Calculation: {_markdown_text(component.get('calculation', 'Not recorded.'))}",
            "",
            "Observed normalized factors:",
            "",
        ])
        factors = component.get("factors", {})
        lines.extend(f"- {_markdown_text(name)}: {float(value):.1f}/100 {snapshot_ref}" for name, value in factors.items())
        if not factors:
            lines.append(f"- No factor was available. {snapshot_ref}")

    udi = explanation.get("udi", {})
    lines.extend(["", "## UDI diagnostic", "", f"{_markdown_text(udi.get('explanation', ''))} {snapshot_ref}", ""])
    for name, value in udi.get("factors", {}).items():
        lines.append(f"- {_markdown_text(name).title()}: {float(value):.1f}/100 {snapshot_ref}")

    lines.extend([
        "",
        "## Observable market profile",
        "",
        f"The imported corpus contains **{market['books']} books** with a median observed price of **{_currency(market['median_price'])}**, "
        f"median rating of **{_number(market['median_rating'], decimals=2)}**, and median displayed review count of **{_number(market['median_reviews'], decimals=0)}**. "
        f"The top three books hold **{_number(market['top_three_review_share'])}%** of displayed reviews. Evidence: {_book_refs(sorted_books) or 'no book records'}.",
        "",
        "| Book evidence | Title | Price | Rating | Displayed reviews | BSR |",
        "|---|---|---:|---:|---:|---:|",
    ])
    for row in sorted_books:
        lines.append(
            f"| {_ref('B', int(row['id']))} | {_markdown_text(row['title'])} | "
            f"{_currency(row.get('price'))} | "
            f"{_number(row.get('rating'), decimals=1)} | {_number(row.get('review_count'), decimals=0)} | "
            f"{_number(row.get('best_seller_rank'), decimals=0)} |"
        )

    cited_reviews: dict[int, dict[str, object]] = {}
    lines.extend(["", "## Review-linked customer gaps", ""])
    if not pain_rows:
        lines.append("No solvable, review-linked pain-point groups are available. This is an evidence gap, not proof that customers have no unmet needs.")
    for pain in pain_rows:
        pain_ref = _ref("P", int(pain["id"]))
        lines.extend([
            f"### {_markdown_text(pain['name'])} {pain_ref}",
            "",
            f"Observed in **{int(pain['reviews'])} reviews across {int(pain['books'])} books**; average severity **{_number(pain['severity'])}/10** and recorded solvability **{_number(pain['solvability'])}/10**. {pain_ref}",
            "",
        ])
        evidence_rows = evidence_repository.pain_point_evidence(int(pain["id"]))[:evidence_per_group]
        for row in evidence_rows:
            cited_reviews[int(row["review_id"])] = row
            lines.append(
                f"> {_ref('R', int(row['review_id']))} · {_ref('B', int(row['book_id']))}: “{_markdown_text(row.get('evidence') or row.get('review'), limit=240)}”"
            )
            lines.append("")

    lines.extend(["## What readers value", ""])
    if not praise_rows:
        lines.append("No review-linked praise-feature groups are available.")
    for feature in praise_rows:
        feature_ref = _ref("F", int(feature["id"]))
        lines.extend([
            f"### {_markdown_text(feature['name'])} {feature_ref}",
            "",
            f"Observed in **{int(feature['reviews'])} reviews across {int(feature['books'])} books** with average strength **{_number(feature['strength'])}/10**. {feature_ref}",
            "",
        ])
        evidence_rows = evidence_repository.praise_evidence(int(feature["id"]))[:evidence_per_group]
        for row in evidence_rows:
            cited_reviews[int(row["review_id"])] = row
            lines.append(
                f"> {_ref('R', int(row['review_id']))} · {_ref('B', int(row['book_id']))}: “{_markdown_text(row.get('evidence') or row.get('review'), limit=240)}”"
            )
            lines.append("")

    lines.extend(["## Validation priorities", ""])
    if warnings:
        lines.extend(f"- Resolve the evidence limitation recorded in {snapshot_ref}: {_markdown_text(warning)}" for warning in warnings)
    for pain in pain_rows[:3]:
        lines.append(f"- Validate a specific solution for {_ref('P', int(pain['id']))} with target readers before treating it as a product requirement.")
    if not warnings and not pain_rows:
        lines.append("- Collect review-linked customer evidence before advancing this niche.")

    lines.extend([
        "",
        "## Evidence ledger",
        "",
        f"### Evidence S{snapshot.id}",
        "",
        f"Score snapshot `{snapshot.id}` · version `{_markdown_text(snapshot.scoring_version)}` · calculated `{snapshot.calculated_at.isoformat()}`. "
        "The snapshot stores component inputs, formulas, weights, confidence parts, warnings, UDI factors, and any human override.",
        "",
    ])
    for row in sorted_books:
        lines.extend([
            f"### Evidence B{int(row['id'])}",
            "",
            f"Imported book record: **{_markdown_text(row['title'])}** · source identifier `{_markdown_text(row.get('source_identifier') or 'not supplied')}`.",
            "",
        ])
    for pain in pain_rows:
        lines.extend([
            f"### Evidence P{int(pain['id'])}",
            "",
            f"Canonical solvable pain-point group: **{_markdown_text(pain['name'])}**. {_markdown_text(pain.get('description') or '')}",
            "",
        ])
    for feature in praise_rows:
        lines.extend([
            f"### Evidence F{int(feature['id'])}",
            "",
            f"Canonical praise-feature group: **{_markdown_text(feature['name'])}**. {_markdown_text(feature.get('description') or '')}",
            "",
        ])
    for review_id, row in sorted(cited_reviews.items()):
        lines.extend([
            f"### Evidence R{review_id}",
            "",
            f"Imported review record linked to {_ref('B', int(row['book_id']))}; rating {_number(row.get('rating'), decimals=0)}. "
            f"Evidence excerpt: “{_markdown_text(row.get('evidence') or row.get('review'), limit=280)}”",
            "",
        ])
    lines.extend([
        "## Method boundary",
        "",
        "Scores are decision aids derived from supplied observations. Missing data is not estimated. Displayed review counts and BSR values are observations, not sales estimates. Review excerpts support research findings but do not prove future demand.",
        "",
    ])

    return OpportunityReport(
        niche_id=niche_id,
        snapshot_id=snapshot.id,
        file_name=f"{_slug(niche.name)}-opportunity-report-s{snapshot.id}.md",
        markdown="\n".join(lines),
        warnings=tuple(warnings),
        cited_review_ids=tuple(sorted(cited_reviews)),
    )
