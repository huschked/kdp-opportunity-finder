"""Provider selection isolated from UI and analysis orchestration."""

from __future__ import annotations

import os

from config.settings import Settings, get_settings
from llm.base import LLMProvider
from llm.mock_provider import MockProvider
from llm.openai_provider import OpenAIProvider


def build_provider(name: str | None = None, settings: Settings | None = None) -> LLMProvider:
    settings = settings or get_settings()
    provider_name = (name or settings.llm_provider).strip().casefold()
    if provider_name == "mock":
        return MockProvider()
    if provider_name == "openai":
        return OpenAIProvider(api_key=os.getenv("OPENAI_API_KEY", ""), model=settings.openai_model)
    raise ValueError(f"Unsupported LLM provider: {provider_name}")
