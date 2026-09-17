"""Deterministic canonicalization used by mock mode and as a safe baseline."""

from __future__ import annotations

from collections import defaultdict

from llm.schemas import (
    PainCluster,
    PainClusterBatch,
    PainPointExtraction,
    PraiseCluster,
    PraiseClusterBatch,
    PraiseExtraction,
)


PAIN_RULES: tuple[tuple[tuple[str, ...], str, str, str], ...] = (
    (("example", "worked", "theoretical", "theory", "real-world", "layout"),
     "Not enough practical examples",
     "Readers need concrete examples that show how to apply the material.",
     "Add worked examples, realistic scenarios, and step-by-step applications."),
    (("diagram", "illustration", "visual", "photo", "image"),
     "Not enough visual guidance",
     "Readers report that visual explanation is missing or insufficient.",
     "Add purposeful diagrams, labeled illustrations, and visual comparisons."),
    (("outdated", "out of date", "old information", "current"),
     "Outdated information",
     "Readers identify information that is no longer current.",
     "Verify every time-sensitive section and clearly date the edition."),
    (("exercise", "workbook", "practice", "worksheet"),
     "Not enough exercises or practice",
     "Readers want structured opportunities to practice the material.",
     "Add exercises, answer guidance, and reusable worksheets."),
    (("checklist", "quick reference", "reference sheet"),
     "Missing checklists or quick reference",
     "Readers want concise tools they can use while acting on the guidance.",
     "Add checklists, quick-reference tables, and printable summaries."),
    (("advanced", "confusing", "beginner", "assumes knowledge", "jargon"),
     "Too advanced for beginners",
     "Readers struggle because prerequisite knowledge is assumed.",
     "Define terms, stage complexity, and add beginner-first explanations."),
    (("organized", "organization", "disorganized", "structure", "repetitive"),
     "Poor organization",
     "Readers struggle to find or follow information because of structure.",
     "Reorganize around reader tasks with a clear progression and index."),
    (("damaged", "shipping", "arrived", "delivery"),
     "Shipping or physical damage",
     "The complaint concerns fulfillment rather than book content.",
     "Not a content differentiation opportunity."),
    (("seller", "refund", "charged"),
     "Seller or transaction issue",
     "The complaint concerns the seller or transaction rather than the book.",
     "Not a content differentiation opportunity."),
    (("wrong book", "not what i expected", "bought by mistake"),
     "Buyer mismatch",
     "The buyer selected a product that did not match their needs.",
     "Clarify positioning and intended reader; do not treat this as a content gap."),
)


PRAISE_RULES: tuple[tuple[tuple[str, ...], str, str], ...] = (
    (("step-by-step", "step by step", "easy to follow"),
     "Clear step-by-step instruction", "Readers value an explicit sequence of actions."),
    (("diagram", "illustration", "visual", "photo", "chart"),
     "Effective visual guidance", "Readers value visuals that clarify the material."),
    (("checklist", "quick reference", "table"),
     "Useful reference tools", "Readers value concise tools they can use during practice."),
    (("clear", "simple", "explained"),
     "Clear explanations", "Readers value accessible explanations."),
    (("practical", "actionable", "real-world", "example"),
     "Practical application", "Readers value guidance that transfers into action."),
    (("comprehensive", "thorough", "complete"),
     "Comprehensive coverage", "Readers value breadth and completeness."),
    (("seasonal", "calendar"),
     "Useful seasonal organization", "Readers value guidance organized around timing."),
)


def _matching_rule(text: str, rules: tuple) -> tuple | None:
    lowered = text.casefold()
    for rule in rules:
        if any(term in lowered for term in rule[0]):
            return rule
    return None


def cluster_pain_points(candidates: list[PainPointExtraction]) -> PainClusterBatch:
    grouped: dict[str, list[str]] = defaultdict(list)
    metadata: dict[str, tuple[str, str | None]] = {}
    for candidate in candidates:
        rule = _matching_rule(f"{candidate.name} {candidate.description}", PAIN_RULES)
        if rule:
            _, canonical, description, solution = rule
        else:
            canonical = candidate.name.strip().capitalize()
            description = candidate.description
            solution = candidate.suggested_solution
        if candidate.name not in grouped[canonical]:
            grouped[canonical].append(candidate.name)
        metadata[canonical] = (description, solution)
    return PainClusterBatch(clusters=[
        PainCluster(
            canonical_name=canonical,
            description=metadata[canonical][0],
            member_names=members,
            suggested_solution=metadata[canonical][1],
        )
        for canonical, members in sorted(grouped.items())
    ])


def cluster_praise_features(candidates: list[PraiseExtraction]) -> PraiseClusterBatch:
    grouped: dict[str, list[str]] = defaultdict(list)
    descriptions: dict[str, str] = {}
    for candidate in candidates:
        rule = _matching_rule(f"{candidate.name} {candidate.description}", PRAISE_RULES)
        if rule:
            _, canonical, description = rule
        else:
            canonical = candidate.name.strip().capitalize()
            description = candidate.description
        if candidate.name not in grouped[canonical]:
            grouped[canonical].append(candidate.name)
        descriptions[canonical] = description
    return PraiseClusterBatch(clusters=[
        PraiseCluster(
            canonical_name=canonical,
            description=descriptions[canonical],
            member_names=members,
        )
        for canonical, members in sorted(grouped.items())
    ])

