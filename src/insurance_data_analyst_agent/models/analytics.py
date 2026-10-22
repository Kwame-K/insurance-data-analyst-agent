from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class Dimension(StrEnum):
    PROVINCE = "province"
    LINE_OF_BUSINESS = "line_of_business"
    UNDERWRITING_YEAR = "underwriting_year"


class ChartType(StrEnum):
    GROUPED_BAR = "grouped_bar"
    LINE = "line"
    TABLE = "table"


ALLOWED_PROVINCES = {
    "QC",
    "ON",
    "BC",
    "AB",
}

ALLOWED_LINES_OF_BUSINESS = {
    "commercial_property",
    "commercial_auto",
    "general_liability",
}


def _check_years(years: list[int], field_name: str, label: str) -> None:
    if len(set(years)) != len(years):
        raise ValueError(f"{field_name} must not contain duplicates.")

    if any(year < 2000 or year > 2100 for year in years):
        raise ValueError(f"Each {label} must be between 2000 and 2100.")


def _check_provinces(provinces: list[str] | None) -> list[str] | None:
    if provinces is None:
        return None

    invalid_provinces = [
        province for province in provinces if province not in ALLOWED_PROVINCES
    ]

    if invalid_provinces:
        raise ValueError(
            f"Unsupported province filters: {', '.join(invalid_provinces)}."
        )

    return provinces


def _check_lines_of_business(
    lines_of_business: list[str] | None,
) -> list[str] | None:
    if lines_of_business is None:
        return None

    invalid_lines_of_business = [
        line_of_business
        for line_of_business in lines_of_business
        if line_of_business not in ALLOWED_LINES_OF_BUSINESS
    ]

    if invalid_lines_of_business:
        raise ValueError(
            f"Unsupported line-of-business filters: {', '.join(invalid_lines_of_business)}."
        )

    return lines_of_business


class LossRatioRequest(BaseModel):
    underwriting_years: list[int] = Field(
        min_length=1,
        max_length=10,
        description="Underwriting years included in the analysis.",
    )
    dimensions: list[Dimension] = Field(
        default=[Dimension.PROVINCE, Dimension.LINE_OF_BUSINESS],
        min_length=1,
        max_length=3,
    )
    provinces: list[str] | None = None
    lines_of_business: list[str] | None = None

    @model_validator(mode="after")
    def validate_years(self) -> LossRatioRequest:
        _check_years(self.underwriting_years, "underwriting_years", "underwriting year")
        return self

    @field_validator("provinces")
    @classmethod
    def validate_provinces(
        cls,
        provinces: list[str] | None,
    ) -> list[str] | None:
        return _check_provinces(provinces)

    @field_validator("lines_of_business")
    @classmethod
    def validate_lines_of_business(
        cls,
        lines_of_business: list[str] | None,
    ) -> list[str] | None:
        return _check_lines_of_business(lines_of_business)


class ClaimFrequencyRequest(BaseModel):
    """Arguments of get_claim_frequency_trend (claims per exposure unit)."""

    model_config = ConfigDict(extra="forbid")

    years: list[int] = Field(
        min_length=2,
        max_length=10,
        description="Exposure and claim years compared in the trend (at least two).",
    )
    dimensions: list[Dimension] = Field(
        default_factory=list,
        max_length=2,
        description="Optional segments: province and/or line_of_business.",
    )
    provinces: list[str] | None = None
    lines_of_business: list[str] | None = None

    @model_validator(mode="after")
    def validate_years(self) -> ClaimFrequencyRequest:
        _check_years(self.years, "years", "year")
        return self

    @field_validator("dimensions")
    @classmethod
    def validate_dimensions(cls, dimensions: list[Dimension]) -> list[Dimension]:
        if Dimension.UNDERWRITING_YEAR in dimensions:
            raise ValueError(
                "underwriting_year is not a valid dimension for a claim frequency trend."
            )

        if len(set(dimensions)) != len(dimensions):
            raise ValueError("dimensions must not contain duplicates.")

        return dimensions

    @field_validator("provinces")
    @classmethod
    def validate_provinces(
        cls,
        provinces: list[str] | None,
    ) -> list[str] | None:
        return _check_provinces(provinces)

    @field_validator("lines_of_business")
    @classmethod
    def validate_lines_of_business(
        cls,
        lines_of_business: list[str] | None,
    ) -> list[str] | None:
        return _check_lines_of_business(lines_of_business)


class UnderwritingYearRequest(BaseModel):
    """Shared arguments of the underwriting-year tools (policy cohort basis)."""

    model_config = ConfigDict(extra="forbid")

    underwriting_years: list[int] = Field(
        min_length=1,
        max_length=10,
        description="Underwriting years included in the analysis.",
    )
    dimensions: list[Dimension] = Field(
        default_factory=lambda: [Dimension.UNDERWRITING_YEAR],
        min_length=1,
        max_length=3,
    )
    provinces: list[str] | None = None
    lines_of_business: list[str] | None = None

    @model_validator(mode="after")
    def validate_years(self) -> Self:
        _check_years(self.underwriting_years, "underwriting_years", "underwriting year")
        return self

    @field_validator("dimensions")
    @classmethod
    def validate_dimensions(cls, dimensions: list[Dimension]) -> list[Dimension]:
        if len(set(dimensions)) != len(dimensions):
            raise ValueError("dimensions must not contain duplicates.")

        return dimensions

    @field_validator("provinces")
    @classmethod
    def validate_provinces(
        cls,
        provinces: list[str] | None,
    ) -> list[str] | None:
        return _check_provinces(provinces)

    @field_validator("lines_of_business")
    @classmethod
    def validate_lines_of_business(
        cls,
        lines_of_business: list[str] | None,
    ) -> list[str] | None:
        return _check_lines_of_business(lines_of_business)


class SeverityRequest(UnderwritingYearRequest):
    """Arguments of get_claim_severity (average paid amount per claim)."""


class ExposureSummaryRequest(UnderwritingYearRequest):
    """Arguments of get_exposure_summary."""


class PortfolioQualityRequest(UnderwritingYearRequest):
    """Arguments of get_portfolio_quality_metrics."""


class ToolCallAudit(BaseModel):
    tool_name: str
    validated_arguments: dict[str, Any]
    execution_status: Literal["success", "failed"]


class ChartMetadata(BaseModel):
    chart_type: ChartType
    x: str
    y: str
    series: list[str]
    title: str
    output_path: str | None = None


class AuditMetadata(BaseModel):
    dataset_version: str
    calculation_definition: str
    database_path: str


class AnalyticsResponse(BaseModel):
    question: str
    tool_calls: list[ToolCallAudit]
    raw_results: list[dict[str, Any]]
    answer: str
    chart: ChartMetadata | None = None
    audit: AuditMetadata
