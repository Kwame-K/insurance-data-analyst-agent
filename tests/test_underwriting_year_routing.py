from __future__ import annotations

import pytest

from insurance_data_analyst_agent.llm.fake import FakeLLMClient
from insurance_data_analyst_agent.llm.prompts import TOOL_SELECTION_SYSTEM_PROMPT
from insurance_data_analyst_agent.models.analytics import Dimension
from insurance_data_analyst_agent.models.routing import ARGUMENT_MODELS
from insurance_data_analyst_agent.services.llm_router import LLMRouter
from insurance_data_analyst_agent.services.response_builder import RESPONSE_BUILDERS
from insurance_data_analyst_agent.services.router import (
    ROUTE_RULES,
    UnsupportedQuestionError,
    route_question,
)
from insurance_data_analyst_agent.tools.registry import build_default_tool_registry

AVAILABLE_YEARS = [2023, 2024, 2025]


def test_every_tool_is_wired_everywhere() -> None:
    tool_names = set(ARGUMENT_MODELS)

    assert {rule.tool_name for rule in ROUTE_RULES} == tool_names
    assert len(ROUTE_RULES) == len(tool_names)
    assert set(RESPONSE_BUILDERS) == tool_names
    assert set(build_default_tool_registry().list_tool_names()) == tool_names
    for name in tool_names:
        assert name in TOOL_SELECTION_SYSTEM_PROMPT


def test_severity_question_gets_underwriting_year_dimension() -> None:
    selection = route_question(
        "Show the claim severity by line of business for 2025.", AVAILABLE_YEARS
    )

    assert selection.tool_name == "get_claim_severity"
    assert selection.arguments.dimensions == [
        Dimension.LINE_OF_BUSINESS,
        Dimension.UNDERWRITING_YEAR,
    ]
    assert selection.arguments.underwriting_years == [2025]


def test_typographic_apostrophe_is_understood() -> None:
    selection = route_question(
        "Résumé de l\u2019exposition pour 2024.", AVAILABLE_YEARS
    )

    assert selection.tool_name == "get_exposure_summary"


def test_quality_metrics_win_over_the_metrics_they_contain() -> None:
    selection = route_question(
        "Portfolio quality metrics: loss ratio, claim frequency and severity.",
        AVAILABLE_YEARS,
    )

    assert selection.tool_name == "get_portfolio_quality_metrics"


@pytest.mark.parametrize(
    "question",
    [
        "Show the loss ratio and the claim severity.",
        "Show the claim frequency and the exposure summary.",
    ],
)
def test_two_single_metrics_in_one_question_are_rejected(question: str) -> None:
    with pytest.raises(UnsupportedQuestionError, match="one analysis at a time"):
        route_question(question, AVAILABLE_YEARS)


def test_unavailable_year_is_rejected_for_new_tools() -> None:
    with pytest.raises(UnsupportedQuestionError):
        route_question("Show the claim severity for 2031.", AVAILABLE_YEARS)


def test_llm_router_accepts_valid_severity_selection() -> None:
    client = FakeLLMClient(
        response={
            "tool_name": "get_claim_severity",
            "arguments": {
                "underwriting_years": [2024, 2025],
                "dimensions": ["province", "underwriting_year"],
                "provinces": None,
                "lines_of_business": None,
            },
        }
    )

    selection = LLMRouter(client=client)(
        "What is the average claim severity by province?", AVAILABLE_YEARS
    )

    assert selection.tool_name == "get_claim_severity"
    assert selection.arguments.underwriting_years == [2024, 2025]
    assert len(client.calls) == 1


def test_llm_router_falls_back_when_severity_year_is_unavailable() -> None:
    client = FakeLLMClient(
        response={
            "tool_name": "get_claim_severity",
            "arguments": {"underwriting_years": [2031]},
        }
    )

    selection = LLMRouter(client=client)(
        "What is the average claim severity by province?", AVAILABLE_YEARS
    )

    assert selection.tool_name == "get_claim_severity"
    assert selection.arguments.underwriting_years == AVAILABLE_YEARS


def test_llm_cannot_select_new_tools_for_threshold_questions() -> None:
    client = FakeLLMClient(
        response={
            "tool_name": "get_portfolio_quality_metrics",
            "arguments": {"underwriting_years": [2025]},
        }
    )

    with pytest.raises(UnsupportedQuestionError, match="threshold or alert"):
        LLMRouter(client=client)(
            "Flag the portfolio quality metrics above 80%.", AVAILABLE_YEARS
        )
