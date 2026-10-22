from __future__ import annotations

import pytest

from insurance_data_analyst_agent.models.analytics import (
    LossRatioRequest,
    UnderwritingYearRequest,
)
from insurance_data_analyst_agent.services.router import (
    UnsupportedQuestionError,
    normalize_text,
    route_question,
)

AVAILABLE_YEARS = [2023, 2024, 2025]


def test_normalize_text_removes_accents_and_normalizes_case() -> None:
    result = normalize_text("  Ratio de Sinistralité au Québec  ")

    assert result == "ratio de sinistralite au quebec"


def test_router_selects_loss_ratio_tool_for_english_question() -> None:
    selection = route_question(
        question=(
            "Show the loss ratio by region and line of business "
            "for the last three underwriting years."
        ),
        available_years=AVAILABLE_YEARS,
    )

    assert selection.tool_name == "get_loss_ratio_by_segment"
    assert isinstance(selection.arguments, (LossRatioRequest, UnderwritingYearRequest))
    assert selection.arguments.underwriting_years == [2023, 2024, 2025]
    assert selection.arguments.provinces is None
    assert selection.arguments.lines_of_business is None


def test_router_extracts_quebec_and_commercial_property() -> None:
    selection = route_question(
        question=(
            "Show the paid loss ratio for commercial property in Québec for 2025."
        ),
        available_years=AVAILABLE_YEARS,
    )

    assert selection.tool_name == "get_loss_ratio_by_segment"
    assert isinstance(selection.arguments, (LossRatioRequest, UnderwritingYearRequest))
    assert selection.arguments.underwriting_years == [2025]
    assert selection.arguments.provinces == ["QC"]
    assert selection.arguments.lines_of_business == ["commercial_property"]


def test_router_supports_french_question() -> None:
    selection = route_question(
        question=(
            "Afficher le ratio de sinistralité pour la propriété "
            "commerciale au Québec pour 2024 et 2025."
        ),
        available_years=AVAILABLE_YEARS,
    )

    assert selection.tool_name == "get_loss_ratio_by_segment"
    assert isinstance(selection.arguments, (LossRatioRequest, UnderwritingYearRequest))
    assert selection.arguments.underwriting_years == [2024, 2025]
    assert selection.arguments.provinces == ["QC"]
    assert selection.arguments.lines_of_business == ["commercial_property"]


def test_router_extracts_multiple_provinces() -> None:
    selection = route_question(
        question=("Show loss ratio for Quebec and Alberta in 2025."),
        available_years=AVAILABLE_YEARS,
    )

    assert selection.arguments.provinces == ["QC", "AB"]
    assert isinstance(selection.arguments, (LossRatioRequest, UnderwritingYearRequest))
    assert selection.arguments.underwriting_years == [2025]


def test_router_uses_last_three_years_by_default() -> None:
    selection = route_question(
        question="Show loss ratio by province.",
        available_years=AVAILABLE_YEARS,
    )

    assert isinstance(selection.arguments, (LossRatioRequest, UnderwritingYearRequest))
    assert selection.arguments.underwriting_years == [2023, 2024, 2025]


def test_router_rejects_unsupported_question() -> None:
    with pytest.raises(
        UnsupportedQuestionError,
        match="Unsupported question",
    ):
        route_question(
            question="What is the average premium by broker?",
            available_years=AVAILABLE_YEARS,
        )


def test_router_rejects_empty_question() -> None:
    with pytest.raises(
        UnsupportedQuestionError,
        match="Question must not be empty",
    ):
        route_question(
            question="   ",
            available_years=AVAILABLE_YEARS,
        )


def test_router_rejects_question_when_no_years_are_available() -> None:
    with pytest.raises(
        UnsupportedQuestionError,
        match="No underwriting years are available",
    ):
        route_question(
            question="Show loss ratio by region.",
            available_years=[],
        )


def test_router_rejects_year_not_available_in_database() -> None:
    with pytest.raises(
        UnsupportedQuestionError,
        match="Requested underwriting years are not available: 2021",
    ):
        route_question(
            question="Show loss ratio for 2021.",
            available_years=AVAILABLE_YEARS,
        )
