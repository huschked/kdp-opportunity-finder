"""Strict schemas shared by every review-analysis provider."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


SCHEMA_VERSION = "1"
PROMPT_VERSION = "review-extraction-1"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Sentiment(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    MIXED = "mixed"
    NEUTRAL = "neutral"


class ComplaintCategory(StrEnum):
    BOOK_CONTENT = "book_content"
    BOOK_DESIGN = "book_design"
    FORMAT_USABILITY = "format_usability"
    SHIPPING = "shipping"
    SELLER = "seller"
    BUYER_MISMATCH = "buyer_mismatch"
    OTHER = "other"


class ReaderSkillLevel(StrEnum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class ReviewForAnalysis(StrictModel):
    review_id: int = Field(gt=0)
    rating: int | None = Field(default=None, ge=1, le=5)
    title: str | None = None
    body: str = Field(min_length=1)


class PainPointExtraction(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=500)
    category: ComplaintCategory
    severity: float = Field(ge=0, le=10)
    solvable_in_book: bool
    solvability_score: float = Field(ge=0, le=10)
    suggested_solution: str | None = Field(default=None, max_length=500)
    evidence_text: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def irrelevant_complaints_are_not_content_solutions(self) -> PainPointExtraction:
        if self.category in {
            ComplaintCategory.SHIPPING,
            ComplaintCategory.SELLER,
            ComplaintCategory.BUYER_MISMATCH,
        } and (self.solvable_in_book or self.solvability_score > 2):
            raise ValueError(
                "Shipping, seller, and buyer-mismatch complaints must have book solvability of 0–2"
            )
        return self


class PraiseExtraction(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=500)
    strength: float = Field(ge=0, le=10)
    evidence_text: str = Field(min_length=1, max_length=500)


class ReviewExtraction(StrictModel):
    review_id: int = Field(gt=0)
    sentiment: Sentiment
    topics: list[str] = Field(default_factory=list, max_length=12)
    features: list[str] = Field(default_factory=list, max_length=12)
    pain_points: list[PainPointExtraction] = Field(default_factory=list, max_length=8)
    praise: list[PraiseExtraction] = Field(default_factory=list, max_length=8)
    desired_outcomes: list[str] = Field(default_factory=list, max_length=10)
    reader_skill_level: ReaderSkillLevel = ReaderSkillLevel.UNKNOWN
    purchase_motivation: str | None = Field(default=None, max_length=500)
    suggested_improvements: list[str] = Field(default_factory=list, max_length=8)
    confidence: float = Field(ge=0, le=1)

    @field_validator("topics", "features", "desired_outcomes", "suggested_improvements")
    @classmethod
    def unique_nonempty_strings(cls, values: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            cleaned = value.strip()
            key = cleaned.casefold()
            if cleaned and key not in seen:
                result.append(cleaned)
                seen.add(key)
        return result


class ReviewBatchExtraction(StrictModel):
    reviews: list[ReviewExtraction]


class PainCluster(StrictModel):
    canonical_name: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=500)
    member_names: list[str] = Field(min_length=1)
    suggested_solution: str | None = Field(default=None, max_length=500)


class PainClusterBatch(StrictModel):
    clusters: list[PainCluster]


class PraiseCluster(StrictModel):
    canonical_name: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=500)
    member_names: list[str] = Field(min_length=1)


class PraiseClusterBatch(StrictModel):
    clusters: list[PraiseCluster]

