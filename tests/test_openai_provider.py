from types import SimpleNamespace

from llm.openai_provider import OpenAIProvider
from llm.schemas import ReviewBatchExtraction, ReviewExtraction, ReviewForAnalysis, Sentiment


class FakeCompletions:
    def __init__(self, parsed):
        self.parsed = parsed
        self.request = None

    def parse(self, **kwargs):
        self.request = kwargs
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(parsed=self.parsed, refusal=None))],
            usage=SimpleNamespace(prompt_tokens=120, completion_tokens=30),
        )


def test_openai_provider_uses_pydantic_parse_and_captures_usage() -> None:
    parsed = ReviewBatchExtraction(reviews=[ReviewExtraction(
        review_id=1, sentiment=Sentiment.POSITIVE, confidence=0.9
    )])
    completions = FakeCompletions(parsed)
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    provider = OpenAIProvider(api_key="", model="test-model", client=client)
    result = provider.analyze_reviews([ReviewForAnalysis(review_id=1, rating=5, body="Very useful")])
    assert result.payload == parsed
    assert result.usage.input_tokens == 120
    assert result.usage.output_tokens == 30
    assert completions.request["response_format"] is ReviewBatchExtraction
