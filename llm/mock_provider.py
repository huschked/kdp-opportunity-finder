"""Deterministic local provider used for development, tests, and free analysis."""

from __future__ import annotations

from analysis.clustering import cluster_pain_points, cluster_praise_features
from llm.base import ProviderResult
from llm.schemas import (
    ComplaintCategory,
    PainClusterBatch,
    PainPointExtraction,
    PraiseClusterBatch,
    PraiseExtraction,
    ReaderSkillLevel,
    ReviewBatchExtraction,
    ReviewExtraction,
    ReviewForAnalysis,
    Sentiment,
)


def _excerpt(text: str, limit: int = 240) -> str:
    compact = " ".join(text.split())
    return compact if len(compact) <= limit else f"{compact[: limit - 1].rstrip()}…"


NEGATIVE_CUES = ("need", "not enough", "missing", "lack", "too ", "confusing", "poor", "outdated", "disorganized", "no ")
POSITIVE_CUES = ("clear", "helpful", "great", "love", "useful", "easy", "excellent", "effective", "practical", "comprehensive")


def _has_contextual_match(text: str, terms: tuple[str, ...], cues: tuple[str, ...]) -> bool:
    for term in terms:
        start = text.find(term)
        if start >= 0:
            window = text[max(0, start - 55) : start + len(term) + 55]
            if any(cue in window for cue in cues):
                return True
    return False


PAIN_PATTERNS: tuple[tuple[tuple[str, ...], str, str, ComplaintCategory, str, float], ...] = (
    (("damaged", "shipping", "arrived", "delivery"), "Shipping or physical damage", "The complaint concerns delivery or physical damage.", ComplaintCategory.SHIPPING, "Not a book-content opportunity.", 1),
    (("seller", "refund", "charged"), "Seller or transaction issue", "The complaint concerns the seller or transaction.", ComplaintCategory.SELLER, "Not a book-content opportunity.", 1),
    (("wrong book", "not what i expected", "bought by mistake"), "Buyer mismatch", "The book did not match this buyer's intended need.", ComplaintCategory.BUYER_MISMATCH, "Clarify the intended reader and positioning.", 2),
    (("outdated", "out of date", "old information"), "Outdated information", "The review reports information that is no longer current.", ComplaintCategory.BOOK_CONTENT, "Update time-sensitive guidance and date the edition.", 9),
    (("diagram", "illustration", "visual", "photo", "image"), "Not enough visual guidance", "The reader wants more visual explanation.", ComplaintCategory.BOOK_DESIGN, "Add labeled diagrams and purposeful visual examples.", 9),
    (("example", "theory", "theoretical", "real-world", "worked"), "Not enough practical examples", "The reader wants concrete applications of the material.", ComplaintCategory.BOOK_CONTENT, "Add worked examples and realistic scenarios.", 9),
    (("exercise", "workbook", "practice", "worksheet"), "Not enough exercises or practice", "The reader wants structured practice.", ComplaintCategory.FORMAT_USABILITY, "Add exercises, worksheets, and answer guidance.", 9),
    (("checklist", "quick reference", "reference sheet"), "Missing checklists or quick reference", "The reader wants concise reusable tools.", ComplaintCategory.FORMAT_USABILITY, "Add checklists and quick-reference tables.", 9),
    (("advanced", "confusing", "assumes knowledge", "jargon"), "Too advanced for beginners", "The explanation assumes too much prior knowledge.", ComplaintCategory.BOOK_CONTENT, "Define terms and stage the material from beginner to advanced.", 8),
    (("disorganized", "organization", "structure", "repetitive"), "Poor organization", "The structure makes the material harder to follow or retrieve.", ComplaintCategory.FORMAT_USABILITY, "Reorganize chapters around reader tasks and progression.", 8),
)

PRAISE_PATTERNS: tuple[tuple[tuple[str, ...], str, str], ...] = (
    (("step-by-step", "step by step", "easy to follow"), "Clear step-by-step instruction", "The reader values an explicit sequence of actions."),
    (("diagram", "illustration", "visual", "photo", "chart"), "Effective visual guidance", "The reader values visuals that clarify the material."),
    (("checklist", "quick reference", "table"), "Useful reference tools", "The reader values concise reusable tools."),
    (("clear", "simple", "explained"), "Clear explanations", "The reader values accessible explanations."),
    (("practical", "actionable", "real-world", "example"), "Practical application", "The reader values guidance that transfers into action."),
    (("comprehensive", "thorough", "complete"), "Comprehensive coverage", "The reader values breadth and completeness."),
)


class MockProvider:
    name = "mock"
    model = "deterministic-rules-v1"

    def analyze_reviews(self, reviews: list[ReviewForAnalysis]) -> ProviderResult[ReviewBatchExtraction]:
        return ProviderResult(payload=ReviewBatchExtraction(reviews=[self._analyze(review) for review in reviews]))

    def cluster_pain_points(self, candidates: list[PainPointExtraction]) -> ProviderResult[PainClusterBatch]:
        return ProviderResult(payload=cluster_pain_points(candidates))

    def cluster_praise_features(self, candidates: list[PraiseExtraction]) -> ProviderResult[PraiseClusterBatch]:
        return ProviderResult(payload=cluster_praise_features(candidates))

    def _analyze(self, review: ReviewForAnalysis) -> ReviewExtraction:
        text = f"{review.title or ''} {review.body}".strip()
        lowered = text.casefold()
        pain: list[PainPointExtraction] = []
        praise: list[PraiseExtraction] = []
        for terms, name, description, category, solution, solvability in PAIN_PATTERNS:
            irrelevant = category in {ComplaintCategory.SHIPPING, ComplaintCategory.SELLER, ComplaintCategory.BUYER_MISMATCH}
            matched = any(term in lowered for term in terms)
            negative_match = _has_contextual_match(lowered, terms, NEGATIVE_CUES)
            low_rating_match = (review.rating or 3) <= 2 and matched and not _has_contextual_match(lowered, terms, POSITIVE_CUES)
            if matched and (irrelevant or negative_match or low_rating_match):
                pain.append(PainPointExtraction(
                    name=name,
                    description=description,
                    category=category,
                    severity=float(max(2, 7 - (review.rating or 3))),
                    solvable_in_book=category not in {ComplaintCategory.SHIPPING, ComplaintCategory.SELLER, ComplaintCategory.BUYER_MISMATCH},
                    solvability_score=float(solvability),
                    suggested_solution=solution,
                    evidence_text=_excerpt(review.body),
                ))
        positive_context = (review.rating or 3) >= 4 or any(word in lowered for word in ("love", "great", "helpful", "excellent", "useful"))
        if positive_context:
            for terms, name, description in PRAISE_PATTERNS:
                if _has_contextual_match(lowered, terms, POSITIVE_CUES):
                    praise.append(PraiseExtraction(name=name, description=description, strength=float(min(10, (review.rating or 4) + 4)), evidence_text=_excerpt(review.body)))
        if (review.rating or 3) <= 2 and not pain:
            pain.append(PainPointExtraction(
                name="Incomplete or unclear content", description="The low-rating review indicates a content or clarity gap.",
                category=ComplaintCategory.BOOK_CONTENT, severity=float(8 - (review.rating or 2)), solvable_in_book=True,
                solvability_score=7, suggested_solution="Clarify the weak sections and add supporting examples.", evidence_text=_excerpt(review.body),
            ))
        if pain and (praise or (review.rating or 3) >= 4):
            sentiment = Sentiment.MIXED
        elif pain or (review.rating or 3) <= 2:
            sentiment = Sentiment.NEGATIVE
        elif praise or (review.rating or 3) >= 4:
            sentiment = Sentiment.POSITIVE
        else:
            sentiment = Sentiment.NEUTRAL
        skill = ReaderSkillLevel.UNKNOWN
        if "beginner" in lowered or "new to" in lowered:
            skill = ReaderSkillLevel.BEGINNER
        elif "advanced" in lowered or "experienced" in lowered:
            skill = ReaderSkillLevel.ADVANCED
        topics = sorted({item.category.value.replace("_", " ") for item in pain})
        features = sorted({item.name for item in praise})
        outcomes = ["Apply the guidance successfully"] if any(word in lowered for word in ("practical", "apply", "use", "learn")) else []
        purchase_motivation = None
        if "beginner" in lowered or "new to" in lowered:
            purchase_motivation = "Learn the topic as a beginner"
        elif "reference" in lowered:
            purchase_motivation = "Use the book as an ongoing reference"
        elif "learn" in lowered:
            purchase_motivation = "Learn or improve at the topic"
        return ReviewExtraction(
            review_id=review.review_id, sentiment=sentiment, topics=topics, features=features,
            pain_points=pain, praise=praise, desired_outcomes=outcomes, reader_skill_level=skill,
            purchase_motivation=purchase_motivation, suggested_improvements=[item.suggested_solution for item in pain if item.solvable_in_book and item.suggested_solution],
            confidence=0.78,
        )
