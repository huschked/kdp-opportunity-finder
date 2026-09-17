"""Optional OpenAI provider using SDK-native Pydantic Structured Outputs."""

from __future__ import annotations

import json
from typing import Any, TypeVar

from pydantic import BaseModel

from llm.base import ProviderContractError, ProviderResult, ProviderUsage
from llm.prompts import PAIN_CLUSTER_SYSTEM_PROMPT, PRAISE_CLUSTER_SYSTEM_PROMPT, REVIEW_SYSTEM_PROMPT
from llm.schemas import PainClusterBatch, PainPointExtraction, PraiseClusterBatch, PraiseExtraction, ReviewBatchExtraction, ReviewForAnalysis

T = TypeVar("T", bound=BaseModel)


class OpenAIProvider:
    name = "openai"

    def __init__(self, *, api_key: str, model: str, client: Any | None = None) -> None:
        if not api_key and client is None:
            raise ValueError("OPENAI_API_KEY is required when the OpenAI provider is selected.")
        if client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise RuntimeError("Install the openai package to use the OpenAI provider.") from exc
            client = OpenAI(api_key=api_key, max_retries=2)
        self.client = client
        self.model = model

    def _parse(self, system_prompt: str, payload: object, schema: type[T]) -> ProviderResult[T]:
        completion = self.client.chat.completions.parse(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            response_format=schema,
        )
        message = completion.choices[0].message
        parsed = getattr(message, "parsed", None)
        if parsed is None:
            refusal = getattr(message, "refusal", None)
            raise ProviderContractError(refusal or "Provider returned no parsed structured result.")
        usage = getattr(completion, "usage", None)
        return ProviderResult(
            payload=parsed,
            usage=ProviderUsage(
                input_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
                output_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
            ),
        )

    def analyze_reviews(self, reviews: list[ReviewForAnalysis]) -> ProviderResult[ReviewBatchExtraction]:
        return self._parse(REVIEW_SYSTEM_PROMPT, [review.model_dump(mode="json") for review in reviews], ReviewBatchExtraction)

    def cluster_pain_points(self, candidates: list[PainPointExtraction]) -> ProviderResult[PainClusterBatch]:
        return self._parse(PAIN_CLUSTER_SYSTEM_PROMPT, [candidate.model_dump(mode="json") for candidate in candidates], PainClusterBatch)

    def cluster_praise_features(self, candidates: list[PraiseExtraction]) -> ProviderResult[PraiseClusterBatch]:
        return self._parse(PRAISE_CLUSTER_SYSTEM_PROMPT, [candidate.model_dump(mode="json") for candidate in candidates], PraiseClusterBatch)
