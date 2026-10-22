from __future__ import annotations

from insurance_data_analyst_agent.llm.base import (
    LLMClientError,
)
from insurance_data_analyst_agent.llm.fake import (
    FakeLLMClient,
)
from insurance_data_analyst_agent.models.analytics import (
    LossRatioRequest,
    UnderwritingYearRequest,
)
from insurance_data_analyst_agent.services.llm_router import (
    LLMRouter,
)

AVAILABLE_YEARS = [2023, 2024, 2025]


def test_llm_router_uses_valid_llm_tool_selection() -> None:
    client = FakeLLMClient(
        response={
            "tool_name": "get_loss_ratio_by_segment",
            "arguments": {
                "underwriting_years": [2025],
                "dimensions": [
                    "province",
                    "line_of_business",
                    "underwriting_year",
                ],
                "provinces": ["QC"],
                "lines_of_business": ["commercial_property"],
            },
        }
    )

    router = LLMRouter(client=client)

    selection = router(
        "Show paid loss ratio for commercial property in Quebec.",
        AVAILABLE_YEARS,
    )

    assert selection.tool_name == "get_loss_ratio_by_segment"
    assert isinstance(selection.arguments, (LossRatioRequest, UnderwritingYearRequest))
    assert selection.arguments.underwriting_years == [2025]
    assert selection.arguments.provinces == ["QC"]
    assert selection.arguments.lines_of_business == ["commercial_property"]
    assert len(client.calls) == 1


def test_llm_router_falls_back_when_client_is_unavailable() -> None:
    client = FakeLLMClient(error=LLMClientError("Provider temporarily unavailable."))

    router = LLMRouter(client=client)

    selection = router(
        "Show paid loss ratio for Quebec in 2025.",
        AVAILABLE_YEARS,
    )

    assert selection.tool_name == "get_loss_ratio_by_segment"
    assert isinstance(selection.arguments, (LossRatioRequest, UnderwritingYearRequest))
    assert selection.arguments.underwriting_years == [2025]
    assert selection.arguments.provinces == ["QC"]


def test_llm_router_falls_back_when_tool_name_is_invalid() -> None:
    client = FakeLLMClient(
        response={
            "tool_name": "run_arbitrary_sql",
            "arguments": {
                "sql": "SELECT * FROM claims",
            },
        }
    )

    router = LLMRouter(client=client)

    selection = router(
        "Show paid loss ratio for Quebec in 2025.",
        AVAILABLE_YEARS,
    )

    assert selection.tool_name == "get_loss_ratio_by_segment"
    assert isinstance(selection.arguments, (LossRatioRequest, UnderwritingYearRequest))
    assert selection.arguments.underwriting_years == [2025]
    assert selection.arguments.provinces == ["QC"]


def test_llm_router_falls_back_when_arguments_are_invalid() -> None:
    client = FakeLLMClient(
        response={
            "tool_name": "get_loss_ratio_by_segment",
            "arguments": {
                "underwriting_years": [2025],
                "dimensions": [
                    "province",
                    "line_of_business",
                    "underwriting_year",
                ],
                "provinces": ["US"],
                "lines_of_business": None,
            },
        }
    )

    router = LLMRouter(client=client)

    selection = router(
        "Show paid loss ratio for Quebec in 2025.",
        AVAILABLE_YEARS,
    )

    assert selection.tool_name == "get_loss_ratio_by_segment"
    assert isinstance(selection.arguments, (LossRatioRequest, UnderwritingYearRequest))
    assert selection.arguments.underwriting_years == [2025]
    assert selection.arguments.provinces == ["QC"]


def test_llm_router_falls_back_when_year_is_not_available() -> None:
    client = FakeLLMClient(
        response={
            "tool_name": "get_loss_ratio_by_segment",
            "arguments": {
                "underwriting_years": [2021],
                "dimensions": [
                    "province",
                    "line_of_business",
                    "underwriting_year",
                ],
                "provinces": ["QC"],
                "lines_of_business": None,
            },
        }
    )

    router = LLMRouter(client=client)

    selection = router(
        "Show paid loss ratio for Quebec in 2025.",
        AVAILABLE_YEARS,
    )

    assert selection.tool_name == "get_loss_ratio_by_segment"
    assert isinstance(selection.arguments, (LossRatioRequest, UnderwritingYearRequest))
    assert selection.arguments.underwriting_years == [2025]
    assert selection.arguments.provinces == ["QC"]
