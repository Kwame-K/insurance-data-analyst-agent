from __future__ import annotations

from types import SimpleNamespace

import pytest

from insurance_data_analyst_agent.llm.base import LLMClientError
from insurance_data_analyst_agent.llm.gemini_client import GeminiLLMClient


class FakeGeminiModels:
    def __init__(self, text: str | None = None, error: Exception | None = None):
        self.text = text
        self.error = error
        self.calls: list[dict] = []

    def generate_content(self, **kwargs: object) -> SimpleNamespace:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return SimpleNamespace(text=self.text)


def build_client(models: FakeGeminiModels) -> GeminiLLMClient:
    return GeminiLLMClient(
        api_key="test-key",
        model="test-model",
        client=SimpleNamespace(models=models),
    )


def call(client: GeminiLLMClient) -> dict:
    return client.generate_tool_selection(
        system_prompt="system", user_question="question"
    )


def test_returns_json_object() -> None:
    models = FakeGeminiModels(text='{"tool_name": "get_loss_ratio_by_segment"}')

    assert call(build_client(models)) == {"tool_name": "get_loss_ratio_by_segment"}
    assert models.calls[0]["model"] == "test-model"
    assert models.calls[0]["contents"] == "question"


def test_wraps_provider_errors() -> None:
    models = FakeGeminiModels(error=RuntimeError("boom"))

    with pytest.raises(LLMClientError, match="Gemini request failed"):
        call(build_client(models))


@pytest.mark.parametrize("text", [None, "", "not json", "[1, 2]"])
def test_rejects_invalid_responses(text: str | None) -> None:
    with pytest.raises(LLMClientError):
        call(build_client(FakeGeminiModels(text=text)))
