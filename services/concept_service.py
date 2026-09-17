"""Evidence-grounded, deterministic book specification generation."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from analysis.scoring import recommendation_label
from db.repositories import EvidenceRepository, NicheRepository, ScoreRepository
from models import AnalysisRun, Book, BookConcept, Review, ReviewAnalysis
from services.report_service import generate_opportunity_report


EVIDENCE_BACKED = "evidence_backed"
ASSUMPTION = "assumption_to_validate"
RISK_REVIEW = "risk_review_required"
SPECIFICATION_VERSION = "1"


@dataclass(frozen=True, slots=True)
class SpecificationArtifact:
    concept_id: int
    niche_id: int
    snapshot_id: int
    file_name: str
    markdown: str
    evidence_backed_count: int
    assumption_count: int
    warning_count: int


def _choice(
    recommendation: str,
    rationale: str,
    evidence_refs: Iterable[str] = (),
    *,
    status: str | None = None,
) -> dict[str, Any]:
    refs = list(dict.fromkeys(evidence_refs))
    return {
        "recommendation": recommendation,
        "rationale": rationale,
        "status": status or (EVIDENCE_BACKED if refs else ASSUMPTION),
        "evidence_refs": refs,
    }


def _aggregate_analysis_signals(
    session: Session,
    niche_id: int,
) -> tuple[dict[str, list[dict[str, Any]]], dict[int, Review]]:
    rows = list(session.execute(
        select(ReviewAnalysis, Review)
        .join(Review, Review.id == ReviewAnalysis.review_id)
        .join(Book, Book.id == Review.book_id)
        .where(Book.niche_id == niche_id)
        .order_by(Review.id)
    ))
    reviews = {review.id: review for _, review in rows}

    def collect(field: str) -> list[dict[str, Any]]:
        grouped: dict[str, dict[str, Any]] = {}
        for analysis, review in rows:
            for value in getattr(analysis, field) or []:
                cleaned = " ".join(value.split())
                if not cleaned:
                    continue
                key = cleaned.casefold()
                grouped.setdefault(key, {"name": cleaned, "review_ids": []})["review_ids"].append(review.id)
        return sorted(
            ({**value, "review_ids": sorted(set(value["review_ids"])), "count": len(set(value["review_ids"]))} for value in grouped.values()),
            key=lambda value: (-value["count"], value["name"].casefold()),
        )

    reader_groups: dict[str, list[int]] = {}
    for analysis, review in rows:
        level = (analysis.reader_skill_level or "").strip().casefold()
        if level and level != "unknown":
            reader_groups.setdefault(level, []).append(review.id)
    readers = sorted(
        ({"name": level, "review_ids": sorted(set(review_ids)), "count": len(set(review_ids))} for level, review_ids in reader_groups.items()),
        key=lambda value: (-value["count"], value["name"]),
    )
    return {
        "topics": collect("topics_json"),
        "outcomes": collect("desired_outcomes_json"),
        "features": collect("features_json"),
        "readers": readers,
    }, reviews


def _review_evidence(review: Review, *, ref: str | None = None, excerpt: str | None = None) -> dict[str, Any]:
    return {
        "ref": ref or f"R{review.id}",
        "type": "review",
        "id": review.id,
        "book_id": review.book_id,
        "rating": review.rating,
        "excerpt": " ".join((excerpt or review.raw_body).split())[:500],
    }


def _refs_for_signal(signal: dict[str, Any], evidence: dict[str, dict[str, Any]], reviews: dict[int, Review]) -> list[str]:
    refs: list[str] = []
    for review_id in signal["review_ids"][:5]:
        ref = f"R{review_id}"
        refs.append(ref)
        evidence.setdefault(ref, _review_evidence(reviews[review_id]))
    return refs


def _flatten_choices(payload: dict[str, Any]) -> list[dict[str, Any]]:
    choices = [
        payload["working_title"],
        payload["target_reader"],
        payload["core_problem"],
        payload["desired_outcome"],
        payload["positioning"],
        *payload["content_plan"],
        *payload["feature_plan"],
        *payload["format_plan"],
    ]
    return choices


def validate_book_specification(payload: dict[str, Any], evidence_rows: list[dict[str, Any]]) -> None:
    valid_refs = {row["ref"] for row in evidence_rows}
    evidence_types = {row["ref"]: row.get("type") for row in evidence_rows}
    design_choices = _flatten_choices(payload)
    for item in [*design_choices, *payload.get("risk_review", [])]:
        refs = item.get("evidence_refs", [])
        unknown = set(refs) - valid_refs
        if unknown:
            raise ValueError(f"Unknown evidence references: {', '.join(sorted(unknown))}")
    for item in design_choices:
        refs = item.get("evidence_refs", [])
        status = item.get("status")
        if status == EVIDENCE_BACKED and not refs:
            raise ValueError("Every evidence-backed design choice must cite evidence")
        if status == EVIDENCE_BACKED and not any(
            evidence_types.get(ref) in {"pain_point", "praise_feature", "review"}
            for ref in refs
        ):
            raise ValueError("Evidence-backed design choices must cite pain, praise, topic, outcome, or review evidence")
        if not refs and status != ASSUMPTION:
            raise ValueError("Unsupported design choices must be labeled as assumptions to validate")
    if not payload.get("risk_review"):
        raise ValueError("Risk and expert-review requirements must be explicit")


def generate_book_specification(session: Session, *, niche_id: int) -> BookConcept:
    niche = NicheRepository(session).get(niche_id)
    if niche is None:
        raise ValueError("Niche not found")
    report = generate_opportunity_report(session, niche_id=niche_id)
    snapshot = ScoreRepository(session).get(report.snapshot_id)
    assert snapshot is not None
    explanations = snapshot.explanation_json or {}
    components = explanations.get("components", {})
    ai_inputs = components.get("ai_suitability", {}).get("inputs", {})
    evidence_repository = EvidenceRepository(session)
    pain_rows = evidence_repository.pain_point_summaries(niche_id)
    praise_rows = evidence_repository.praise_summaries(niche_id)
    signals, analyzed_reviews = _aggregate_analysis_signals(session, niche_id)

    evidence: dict[str, dict[str, Any]] = {
        f"S{snapshot.id}": {
            "ref": f"S{snapshot.id}",
            "type": "score_snapshot",
            "id": snapshot.id,
            "confidence": snapshot.confidence_score,
            "recommendation": recommendation_label(
                snapshot.human_overall_score if snapshot.human_overall_score is not None else snapshot.automated_overall_score,
                snapshot.confidence_score,
            ),
        }
    }

    pain_refs: dict[int, list[str]] = {}
    for pain in pain_rows:
        ref = f"P{pain['id']}"
        supporting = evidence_repository.pain_point_evidence(int(pain["id"]))[:5]
        review_refs: list[str] = []
        for row in supporting:
            review_ref = f"R{row['review_id']}"
            review_refs.append(review_ref)
            evidence.setdefault(review_ref, {
                "ref": review_ref,
                "type": "review",
                "id": int(row["review_id"]),
                "book_id": int(row["book_id"]),
                "rating": row["rating"],
                "excerpt": " ".join(str(row.get("evidence") or row.get("review") or "").split())[:500],
            })
        evidence[ref] = {
            "ref": ref,
            "type": "pain_point",
            "id": int(pain["id"]),
            "name": pain["name"],
            "description": pain.get("description"),
            "review_count": int(pain["reviews"]),
            "book_count": int(pain["books"]),
            "severity": pain["severity"],
            "solvability": pain["solvability"],
            "suggested_solution": pain.get("solution"),
            "review_refs": review_refs,
        }
        pain_refs[int(pain["id"])] = [ref, *review_refs]

    praise_refs: dict[int, list[str]] = {}
    for feature in praise_rows:
        ref = f"F{feature['id']}"
        supporting = evidence_repository.praise_evidence(int(feature["id"]))[:5]
        review_refs: list[str] = []
        for row in supporting:
            review_ref = f"R{row['review_id']}"
            review_refs.append(review_ref)
            evidence.setdefault(review_ref, {
                "ref": review_ref,
                "type": "review",
                "id": int(row["review_id"]),
                "book_id": int(row["book_id"]),
                "rating": row["rating"],
                "excerpt": " ".join(str(row.get("evidence") or row.get("review") or "").split())[:500],
            })
        evidence[ref] = {
            "ref": ref,
            "type": "praise_feature",
            "id": int(feature["id"]),
            "name": feature["name"],
            "description": feature.get("description"),
            "review_count": int(feature["reviews"]),
            "book_count": int(feature["books"]),
            "strength": feature["strength"],
            "review_refs": review_refs,
        }
        praise_refs[int(feature["id"])] = [ref, *review_refs]

    working_title = _choice(
        f"{niche.name}: A practical reader-focused guide",
        "This is a working title pattern only; title-market fit and trademark conflicts have not been validated.",
    )
    if signals["readers"]:
        reader = signals["readers"][0]
        target_reader = _choice(
            f"Readers identifying as {reader['name']}",
            f"This reader level appeared in {reader['count']} analyzed reviews.",
            _refs_for_signal(reader, evidence, analyzed_reviews),
        )
    else:
        target_reader = _choice(
            "Define one primary reader level before outlining",
            "No analyzed review identifies a reliable reader skill level.",
        )

    if pain_rows:
        pain = pain_rows[0]
        core_problem = _choice(
            str(pain["name"]),
            f"This solvable pain appears in {pain['reviews']} reviews across {pain['books']} books.",
            pain_refs[int(pain["id"])],
        )
    else:
        core_problem = _choice(
            "Identify the primary solvable reader problem",
            "No solvable, review-linked pain point is available.",
        )

    if signals["outcomes"]:
        outcome = signals["outcomes"][0]
        desired_outcome = _choice(
            str(outcome["name"]),
            f"This desired outcome appeared in {outcome['count']} analyzed reviews.",
            _refs_for_signal(outcome, evidence, analyzed_reviews),
        )
    else:
        desired_outcome = _choice(
            "Define a specific, observable reader outcome",
            "No desired outcome was extracted from analyzed reviews.",
        )

    if pain_rows and praise_rows:
        pain = pain_rows[0]
        praise = praise_rows[0]
        positioning = _choice(
            f"Address {str(pain['name']).casefold()} while preserving {str(praise['name']).casefold()}",
            "This direction combines the most prevalent solvable gap with the most prevalent valued feature.",
            [*pain_refs[int(pain["id"])], *praise_refs[int(praise["id"])]],
        )
    else:
        positioning = _choice(
            "Validate a differentiated promise against target-reader interviews",
            "The evidence does not yet contain both a recurring solvable gap and a valued feature.",
        )

    content_plan: list[dict[str, Any]] = []
    for signal in signals["topics"][:4]:
        content_plan.append(_choice(
            f"Cover: {signal['name']}",
            f"The topic appeared in {signal['count']} analyzed reviews.",
            _refs_for_signal(signal, evidence, analyzed_reviews),
        ))
    for pain in pain_rows[:3]:
        content_plan.append(_choice(
            f"Resolution module: {pain['name']}",
            str(pain.get("solution") or "Develop and validate a direct response to this recurring gap."),
            pain_refs[int(pain["id"])],
        ))
    if not content_plan:
        content_plan = [
            _choice("Reader orientation and baseline concepts", "No evidence-backed topic sequence is available."),
            _choice("Applied workflow and examples", "Validate the need and sequence with target readers."),
            _choice("Troubleshooting and next steps", "Validate recurring failure modes before drafting."),
        ]

    feature_plan: list[dict[str, Any]] = []
    for feature in praise_rows[:3]:
        feature_plan.append(_choice(
            f"Preserve or improve: {feature['name']}",
            f"Readers praised this feature in {feature['reviews']} reviews across {feature['books']} books.",
            praise_refs[int(feature["id"])],
        ))
    for pain in pain_rows[:3]:
        feature_plan.append(_choice(
            str(pain.get("solution") or f"Add a specific resource addressing {pain['name']}"),
            f"This feature responds directly to the solvable pain point {pain['name']}.",
            pain_refs[int(pain["id"])],
        ))
    if not feature_plan:
        feature_plan.append(_choice(
            "Choose examples, tools, and visual aids after reader validation",
            "No review-linked feature preference or solvable design gap is available.",
        ))

    format_plan: list[dict[str, Any]] = []
    format_signals = [
        item for item in [*pain_rows, *praise_rows]
        if any(term in str(item["name"]).casefold() for term in ("visual", "diagram", "photo", "checklist", "reference", "exercise", "workbook", "practice"))
    ]
    for item in format_signals[:3]:
        if "severity" in item:
            refs = pain_refs[int(item["id"])]
            rationale = "A solvable review-linked gap identifies this presentation need."
        else:
            refs = praise_refs[int(item["id"])]
            rationale = "A review-linked praise feature identifies this presentation preference."
        format_plan.append(_choice(f"Evaluate a format feature for: {item['name']}", rationale, refs))
    if not format_plan:
        format_plan.append(_choice(
            "Validate trim size, length, visuals, and companion materials before production",
            "The available review evidence does not establish a specific physical or digital format requirement.",
        ))

    regulated_hits = list(ai_inputs.get("regulated term hits") or [])
    expertise_hits = list(ai_inputs.get("expertise term hits") or [])
    asset_hits = list(ai_inputs.get("asset term hits") or [])
    risk_review: list[dict[str, Any]] = []
    if regulated_hits or expertise_hits:
        terms = ", ".join([*regulated_hits, *expertise_hits])
        risk_review.append(_choice(
            f"Require qualified expert review for these screened terms: {terms}",
            "The Phase 4 suitability screen found terms associated with regulated or expertise-sensitive content. Keyword screening is not legal or professional clearance.",
            [f"S{snapshot.id}"],
            status=RISK_REVIEW,
        ))
    else:
        risk_review.append(_choice(
            "Complete a topic-specific accuracy, rights, and expert-review assessment",
            "No regulated or expertise-sensitive keyword was detected, but absence of a keyword is not clearance.",
            [f"S{snapshot.id}"],
            status=RISK_REVIEW,
        ))
    if asset_hits:
        risk_review.append(_choice(
            f"Plan rights, sourcing, and quality review for asset signals: {', '.join(asset_hits)}",
            "The suitability screen identified asset-intensive terms.",
            [f"S{snapshot.id}"],
            status=RISK_REVIEW,
        ))

    latest_run_id = session.scalar(
        select(AnalysisRun.id)
        .where(
            AnalysisRun.niche_id == niche_id,
            AnalysisRun.analysis_type == "review_evidence",
            AnalysisRun.status == "completed",
        )
        .order_by(AnalysisRun.completed_at.desc(), AnalysisRun.id.desc())
        .limit(1)
    )
    payload: dict[str, Any] = {
        "version": SPECIFICATION_VERSION,
        "source_snapshot_id": snapshot.id,
        "source_analysis_run_id": latest_run_id,
        "niche_name": niche.name,
        "decision_context": {
            "automated_score": snapshot.automated_overall_score,
            "human_score": snapshot.human_overall_score,
            "confidence": snapshot.confidence_score,
            "recommendation": recommendation_label(
                snapshot.human_overall_score if snapshot.human_overall_score is not None else snapshot.automated_overall_score,
                snapshot.confidence_score,
            ),
        },
        "working_title": working_title,
        "target_reader": target_reader,
        "core_problem": core_problem,
        "desired_outcome": desired_outcome,
        "positioning": positioning,
        "content_plan": content_plan,
        "feature_plan": feature_plan,
        "format_plan": format_plan,
        "risk_review": risk_review,
        "evidence_warnings": list(report.warnings),
        "validation_questions": [],
    }
    assumptions = [item for item in _flatten_choices(payload) if item["status"] == ASSUMPTION]
    payload["validation_questions"] = [
        f"Validate assumption: {item['recommendation']}" for item in assumptions
    ] + [f"Resolve evidence warning: {warning}" for warning in report.warnings]
    evidence_rows = list(evidence.values())
    validate_book_specification(payload, evidence_rows)
    concept = BookConcept(
        niche_id=niche_id,
        analysis_run_id=latest_run_id,
        title=working_title["recommendation"][:500],
        concept_json=payload,
        evidence_json=evidence_rows,
    )
    session.add(concept)
    session.flush()
    return concept


def _md(value: object, *, limit: int | None = None) -> str:
    text = " ".join(str(value or "").split())
    if limit and len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return re.sub(r"([\\`*_[\]<>#|])", r"\\\1", text)


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-") or "book-specification"


def _ref(value: str) -> str:
    return f"[{value}](#evidence-{value.casefold()})"


def _render_choice(lines: list[str], heading: str, item: dict[str, Any]) -> None:
    status_labels = {
        EVIDENCE_BACKED: "Evidence-backed",
        ASSUMPTION: "Assumption to validate",
        RISK_REVIEW: "Risk review required",
    }
    refs = " ".join(_ref(ref) for ref in item.get("evidence_refs", [])) or "No supporting evidence yet"
    lines.extend([
        f"### {_md(heading)}",
        "",
        f"**{status_labels[item['status']]}:** {_md(item['recommendation'])}",
        "",
        f"Rationale: {_md(item['rationale'])}",
        "",
        f"Evidence: {refs}",
        "",
    ])


def render_book_specification(concept: BookConcept) -> SpecificationArtifact:
    payload = concept.concept_json
    evidence_rows = concept.evidence_json or []
    validate_book_specification(payload, evidence_rows)
    context = payload["decision_context"]
    choices = _flatten_choices(payload)
    evidence_backed_count = sum(item["status"] == EVIDENCE_BACKED for item in choices)
    assumption_count = sum(item["status"] == ASSUMPTION for item in choices)
    lines = [
        f"# Book specification: {_md(payload['niche_name'])}",
        "",
        "> Planning draft only. Evidence-backed recommendations still require editorial judgment, fact checking, rights clearance, and reader validation.",
        "",
        f"Generated from score snapshot {_ref(f'S{payload['source_snapshot_id']}')} and specification version `{_md(payload['version'])}`.",
        "",
        "## Decision context",
        "",
        "| Measure | Value |",
        "|---|---:|",
        f"| Automated score | {float(context['automated_score']):.1f}/100 |",
        f"| Human score | {float(context['human_score']):.1f}/100 |" if context.get("human_score") is not None else "| Human score | Not applied |",
        f"| Confidence | {float(context['confidence']):.1f}/100 |",
        f"| Recommendation | **{_md(context['recommendation'])}** |",
        "",
        "## Product brief",
        "",
    ]
    _render_choice(lines, "Working title", payload["working_title"])
    _render_choice(lines, "Target reader", payload["target_reader"])
    _render_choice(lines, "Core problem", payload["core_problem"])
    _render_choice(lines, "Desired outcome", payload["desired_outcome"])
    _render_choice(lines, "Positioning", payload["positioning"])

    for section, key in (
        ("Content plan", "content_plan"),
        ("Feature plan", "feature_plan"),
        ("Format and production plan", "format_plan"),
        ("Risk and expert review", "risk_review"),
    ):
        lines.extend([f"## {section}", ""])
        for index, item in enumerate(payload[key], start=1):
            _render_choice(lines, f"{index}. {item['recommendation']}", item)

    lines.extend(["## Evidence limitations and validation", ""])
    warnings = payload.get("evidence_warnings", [])
    if warnings:
        lines.extend(f"- **Evidence warning:** {_md(warning)} {_ref(f'S{payload['source_snapshot_id']}')}" for warning in warnings)
    else:
        lines.append("- No score-snapshot evidence warnings were recorded.")
    lines.extend(f"- {_md(question)}" for question in payload.get("validation_questions", []))

    lines.extend(["", "## Evidence ledger", ""])
    for row in evidence_rows:
        ref = str(row["ref"])
        lines.extend([f"### Evidence {ref}", ""])
        if row["type"] == "score_snapshot":
            lines.append(
                f"Score snapshot `{row['id']}` with confidence {float(row['confidence']):.1f}/100 and recommendation **{_md(row['recommendation'])}**."
            )
        elif row["type"] == "pain_point":
            lines.append(
                f"Solvable pain point **{_md(row['name'])}**, observed in {row['review_count']} reviews across {row['book_count']} books. "
                f"Supporting reviews: {' '.join(_ref(value) for value in row.get('review_refs', [])) or 'none'}"
            )
        elif row["type"] == "praise_feature":
            lines.append(
                f"Praised feature **{_md(row['name'])}**, observed in {row['review_count']} reviews across {row['book_count']} books. "
                f"Supporting reviews: {' '.join(_ref(value) for value in row.get('review_refs', [])) or 'none'}"
            )
        else:
            lines.append(
                f"Review `{row['id']}` linked to book `{row['book_id']}`; rating {row.get('rating') or 'not supplied'}. "
                f"Excerpt: “{_md(row.get('excerpt'), limit=280)}”"
            )
        lines.append("")

    return SpecificationArtifact(
        concept_id=concept.id,
        niche_id=concept.niche_id,
        snapshot_id=int(payload["source_snapshot_id"]),
        file_name=f"{_slug(payload['niche_name'])}-book-specification-c{concept.id}.md",
        markdown="\n".join(lines),
        evidence_backed_count=evidence_backed_count,
        assumption_count=assumption_count,
        warning_count=len(warnings),
    )
