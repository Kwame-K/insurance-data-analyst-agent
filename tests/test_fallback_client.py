from __future__ import annotations

import pytest

from insurance_data_analyst_agent.llm.base import LLMClientError
from insurance_data_analyst_agent.llm.fake import FakeLLMClient
from insurance_data_analyst_agent.llm.fallback import FallbackLLMClient
from insurance_data_analyst_agent.llm.trace import routing_provider_var
from insurance_data_analyst_agent.services.llm_router import LLMRouter

VALID_SELECTION = {
    "tool_name": "get_loss_ratio_by_segment",
    "arguments": {
        "underwriting_years": [2025],
        "dimensions": ["province", "line_of_business", "underwriting_year"],
        "provinces": None,
        "lines_of_business": None,
    },
}


def call(client: FallbackLLMClient) -> dict:
    return client.generate_tool_selection(
        system_prompt="system", user_question="question"
    )


def test_first_provider_wins() -> None:
    gemini = FakeLLMClient(response=VALID_SELECTION)
    groq = FakeLLMClient(response=VALID_SELECTION)

    call(FallbackLLMClient([("gemini", gemini), ("groq", groq)]))

    assert routing_provider_var.get() == "gemini"
    assert groq.calls == []


def test_falls_back_to_groq_when_gemini_fails() -> None:
    gemini = FakeLLMClient(error=LLMClientError("down"))
    groq = FakeLLMClient(response=VALID_SELECTION)

    result = call(FallbackLLMClient([("gemini", gemini), ("groq", groq)]))

    assert result == VALID_SELECTION
    assert routing_provider_var.get() == "groq"


def test_raises_when_all_providers_fail() -> None:
    client = FallbackLLMClient(
        [
            ("gemini", FakeLLMClient(error=LLMClientError("a"))),
            ("groq", FakeLLMClient(error=LLMClientError("b"))),
        ]
    )

    with pytest.raises(LLMClientError, match="No LLM provider succeeded"):
        call(client)


def test_raises_when_no_provider_configured() -> None:
    with pytest.raises(LLMClientError, match="No LLM provider is configured."):
        call(FallbackLLMClient([]))


def test_router_reports_llm_provider() -> None:
    client = FallbackLLMClient([("gemini", FakeLLMClient(response=VALID_SELECTION))])

    LLMRouter(client=client)("loss ratio 2025", [2024, 2025])

    assert routing_provider_var.get() == "gemini"


def test_router_reports_deterministic_when_all_fail() -> None:
    client = FallbackLLMClient(
        [("gemini", FakeLLMClient(error=LLMClientError("down")))]
    )

    selection = LLMRouter(client=client)("loss ratio 2025", [2024, 2025])

    assert routing_provider_var.get() == "deterministic"
    assert selection.arguments.underwriting_years == [2025]


def test_router_rejects_unavailable_years_and_falls_back() -> None:
    invalid = {
        **VALID_SELECTION,
        "arguments": {**VALID_SELECTION["arguments"], "underwriting_years": [2030]},
    }
    client = FallbackLLMClient([("gemini", FakeLLMClient(response=invalid))])

    LLMRouter(client=client)("loss ratio 2025", [2024, 2025])

    assert routing_provider_var.get() == "deterministic"
