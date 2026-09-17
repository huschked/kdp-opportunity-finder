"""Provider protocol and usage-aware results."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar

from pydantic import BaseModel

from llm.schemas import (
    PainClusterBatch,
    PainPointExtraction,
    PraiseClusterBatch,
    PraiseExtraction,
    ReviewBatchExtraction,
    ReviewForAnalysis,
)


class ProviderContractError(RuntimeError):
    """Raised when a provider returns incomplete or inconsistent structured data."""


@dataclass(frozen=True, slots=True)
class ProviderUsage:
    input_tokens: int = 0
    output_tokens: int = 0

    def __add__(self, other: ProviderUsage) -> ProviderUsage:
        return ProviderUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
        )


PayloadT = TypeVar("PayloadT", bound=BaseModel)


@dataclass(frozen=True, slots=True)
class ProviderResult(Generic[PayloadT]):
    payload: PayloadT
    usage: ProviderUsage = ProviderUsage()


class LLMProvider(Protocol):
    name: str
    model: str

    def analyze_reviews(
        self, reviews: list[ReviewForAnalysis]
    ) -> ProviderResult[ReviewBatchExtraction]: ...

    def cluster_pain_points(
        self, candidates: list[PainPointExtraction]
    ) -> ProviderResult[PainClusterBatch]: ...

    def cluster_praise_features(
        self, candidates: list[PraiseExtraction]
    ) -> ProviderResult[PraiseClusterBatch]: ...

