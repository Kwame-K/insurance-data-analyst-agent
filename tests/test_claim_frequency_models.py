from __future__ import annotations

import pytest
from pydantic import ValidationError

from insurance_data_analyst_agent.models.analytics import (
    ClaimFrequencyRequest,
    Dimension,
    LossRatioRequest,
)


def test_valid_request_with_defaults() -> None:
    request = ClaimFrequencyRequest(years=[2024, 2025])

    assert request.years == [2024, 2025]
    assert request.dimensions == []
    assert request.provinces is None
    assert request.lines_of_business is None


def test_valid_request_with_segments_and_filters() -> None:
    request = ClaimFrequencyRequest(
        years=[2023, 2024, 2025],
        dimensions=[Dimension.PROVINCE, Dimension.LINE_OF_BUSINESS],
        provinces=["QC"],
        lines_of_business=["commercial_property"],
    )

    assert request.dimensions == [Dimension.PROVINCE, Dimension.LINE_OF_BUSINESS]


@pytest.mark.parametrize(
    "years, message",
    [
        ([2025], "at least 2"),
        ([2024, 2024], "must not contain duplicates"),
        ([1999, 2025], "between 2000 and 2100"),
        ([2024, 2101], "between 2000 and 2100"),
        (list(range(2010, 2021)), "at most 10"),
    ],
)
def test_invalid_years_are_rejected(years: list[int], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        ClaimFrequencyRequest(years=years)


def test_underwriting_year_dimension_is_rejected() -> None:
    with pytest.raises(ValidationError, match="underwriting_year is not a valid"):
        ClaimFrequencyRequest(
            years=[2024, 2025],
            dimensions=[Dimension.UNDERWRITING_YEAR],
        )


def test_duplicate_dimensions_are_rejected() -> None:
    with pytest.raises(ValidationError, match="dimensions must not contain duplicates"):
        ClaimFrequencyRequest(
            years=[2024, 2025],
            dimensions=[Dimension.PROVINCE, Dimension.PROVINCE],
        )


def test_unsupported_province_is_rejected() -> None:
    with pytest.raises(ValidationError, match="Unsupported province filters: XX"):
        ClaimFrequencyRequest(years=[2024, 2025], provinces=["XX"])


def test_unsupported_line_of_business_is_rejected() -> None:
    with pytest.raises(ValidationError, match="Unsupported line-of-business filters"):
        ClaimFrequencyRequest(years=[2024, 2025], lines_of_business=["cyber"])


def test_extra_fields_are_forbidden() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ClaimFrequencyRequest.model_validate({"years": [2024, 2025], "sql": "SELECT 1"})


def test_loss_ratio_request_messages_are_unchanged() -> None:
    with pytest.raises(
        ValidationError, match="underwriting_years must not contain duplicates"
    ):
        LossRatioRequest(underwriting_years=[2024, 2024])

    with pytest.raises(
        ValidationError, match="Each underwriting year must be between 2000 and 2100"
    ):
        LossRatioRequest(underwriting_years=[1990])

    with pytest.raises(ValidationError, match="Unsupported province filters: XX"):
        LossRatioRequest(underwriting_years=[2025], provinces=["XX"])
