from __future__ import annotations

import pytest

from insurance_data_analyst_agent.llm.fake import FakeLLMClient
from insurance_data_analyst_agent.models.analytics import (
    ClaimFrequencyRequest,
    Dimension,
)
from insurance_data_analyst_agent.services.llm_router import LLMRouter
from insurance_data_analyst_agent.services.router import (
    UnsupportedQuestionError,
    route_question,
)

AVAILABLE_YEARS = [2023, 2024, 2025]
FREQUENCY = "get_claim_frequency_trend"


def frequency_response(years: list[int]) -> dict[str, object]:
    return {
        "tool_name": FREQUENCY,
        "arguments": {
            "years": years,
            "dimensions": ["province"],
            "provinces": None,
            "lines_of_business": None,
        },
    }


def test_both_segments_are_detected_in_order() -> None:
    selection = route_question(
        "Show claim frequency by line of business and by province.",
        AVAILABLE_YEARS,
    )

    assert isinstance(selection.arguments, ClaimFrequencyRequest)
    assert selection.arguments.dimensions == [
        Dimension.PROVINCE,
        Dimension.LINE_OF_BUSINESS,
    ]


def test_single_available_year_is_rejected() -> None:
    with pytest.raises(UnsupportedQuestionError, match="At least two years"):
        route_question("Show the claim frequency trend.", [2025])


def test_loss_ratio_questions_still_route_to_loss_ratio() -> None:
    selection = route_question(
        "Show the loss ratio by province for 2025.", AVAILABLE_YEARS
    )

    assert selection.tool_name == "get_loss_ratio_by_segment"


def test_llm_router_uses_valid_claim_frequency_selection() -> None:
    client = FakeLLMClient(response=frequency_response([2024, 2025]))

    selection = LLMRouter(client=client)(
        "Show claim frequency by province for 2024 and 2025.",
        AVAILABLE_YEARS,
    )

    assert selection.tool_name == FREQUENCY
    assert isinstance(selection.arguments, ClaimFrequencyRequest)
    assert selection.arguments.years == [2024, 2025]
    assert len(client.calls) == 1


def test_llm_router_falls_back_when_years_are_unavailable() -> None:
    client = FakeLLMClient(response=frequency_response([2020, 2021]))

    selection = LLMRouter(client=client)(
        "Show the claim frequency trend.", AVAILABLE_YEARS
    )

    assert selection.tool_name == FREQUENCY
    assert isinstance(selection.arguments, ClaimFrequencyRequest)
    assert selection.arguments.years == AVAILABLE_YEARS
    assert selection.arguments.dimensions == []


def test_llm_cannot_select_claim_frequency_for_threshold_questions() -> None:
    client = FakeLLMClient(response=frequency_response([2024, 2025]))

    with pytest.raises(UnsupportedQuestionError, match="threshold or alert"):
        LLMRouter(client=client)(
            "Flag segments where claim frequency increased by more than 20%.",
            AVAILABLE_YEARS,
        )
