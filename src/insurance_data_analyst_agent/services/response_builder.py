from __future__ import annotations

from collections.abc import Callable
from typing import Any

from insurance_data_analyst_agent.infrastructure.persistence.access import (
    DataSource,
    describe_data_source,
)
from insurance_data_analyst_agent.models.analytics import (
    AnalyticsResponse,
    AuditMetadata,
    ChartMetadata,
    ChartType,
    ClaimFrequencyRequest,
    Dimension,
    ExposureSummaryRequest,
    LossRatioRequest,
    PortfolioQualityRequest,
    SeverityRequest,
    ToolCallAudit,
)
from insurance_data_analyst_agent.models.routing import (
    CLAIM_FREQUENCY_TOOL,
    EXPOSURE_SUMMARY_TOOL,
    LOSS_RATIO_TOOL,
    PORTFOLIO_QUALITY_TOOL,
    SEVERITY_TOOL,
    ToolSelection,
)
from insurance_data_analyst_agent.tools.claim_frequency import (
    CALCULATION_DEFINITION as CLAIM_FREQUENCY_DEFINITION,
)
from insurance_data_analyst_agent.tools.exposure_summary import (
    CALCULATION_DEFINITION as EXPOSURE_SUMMARY_DEFINITION,
)
from insurance_data_analyst_agent.tools.portfolio_quality import (
    CALCULATION_DEFINITION as PORTFOLIO_QUALITY_DEFINITION,
)
from insurance_data_analyst_agent.tools.severity import (
    CALCULATION_DEFINITION as SEVERITY_DEFINITION,
)


def build_loss_ratio_response(
    question: str,
    request: LossRatioRequest,
    raw_results: list[dict[str, Any]],
    database_path: DataSource,
    dataset_version: str,
) -> AnalyticsResponse:
    if not raw_results:
        answer = (
            "No portfolio records matched the selected underwriting years and filters."
        )
    else:
        highest_loss_ratio = max(
            raw_results,
            key=lambda row: row["loss_ratio"] or 0,
        )

        segment_parts = [
            f"{key}={value}"
            for key, value in highest_loss_ratio.items()
            if key
            in {
                "province",
                "line_of_business",
                "underwriting_year",
            }
        ]

        answer = (
            "The analysis returned "
            f"{len(raw_results)} portfolio segments. "
            f"The highest paid loss ratio is "
            f"{highest_loss_ratio['loss_ratio']:.1%} for "
            f"{', '.join(segment_parts)}. "
            "The ratio is calculated as paid claim amount divided by "
            "written premium."
        )

    return AnalyticsResponse(
        question=question,
        tool_calls=[
            ToolCallAudit(
                tool_name="get_loss_ratio_by_segment",
                validated_arguments=request.model_dump(mode="json"),
                execution_status="success",
            )
        ],
        raw_results=raw_results,
        answer=answer,
        chart=ChartMetadata(
            chart_type=ChartType.GROUPED_BAR,
            x="underwriting_year",
            y="loss_ratio",
            series=["province", "line_of_business"],
            title="Paid loss ratio by province and line of business",
        ),
        audit=AuditMetadata(
            dataset_version=dataset_version,
            calculation_definition=(
                "paid_loss_ratio = paid_claim_amount / written_premium"
            ),
            database_path=describe_data_source(database_path),
        ),
    )


def build_claim_frequency_response(
    question: str,
    request: ClaimFrequencyRequest,
    raw_results: list[dict[str, Any]],
    database_path: DataSource,
    dataset_version: str,
) -> AnalyticsResponse:
    segments = [dimension.value for dimension in request.dimensions]

    if not raw_results:
        answer = "No exposure records matched the selected years and filters."
    else:
        highest = max(raw_results, key=lambda row: row["claim_frequency"] or 0)
        highest_parts = [f"{key}={highest[key]}" for key in ["year", *segments]]

        answer = (
            f"The analysis returned {len(raw_results)} rows for years "
            f"{min(request.years)} to {max(request.years)}. "
            f"The highest claim frequency is {highest['claim_frequency']:.3f} "
            f"claims per exposure unit for {', '.join(highest_parts)}. "
            "The frequency is calculated as claim count divided by "
            "exposure units."
        )

        latest = raw_results[-1]
        if not segments and latest["year_over_year_change"] is not None:
            answer += (
                f" The latest year-over-year change is "
                f"{latest['year_over_year_change']:+.1%}."
            )

    return AnalyticsResponse(
        question=question,
        tool_calls=[
            ToolCallAudit(
                tool_name=CLAIM_FREQUENCY_TOOL,
                validated_arguments=request.model_dump(mode="json"),
                execution_status="success",
            )
        ],
        raw_results=raw_results,
        answer=answer,
        chart=ChartMetadata(
            chart_type=ChartType.LINE,
            x="year",
            y="claim_frequency",
            series=segments,
            title="Claim frequency trend (claims per exposure unit)",
        ),
        audit=AuditMetadata(
            dataset_version=dataset_version,
            calculation_definition=CLAIM_FREQUENCY_DEFINITION,
            database_path=describe_data_source(database_path),
        ),
    )


NO_ROWS_ANSWER = (
    "No portfolio records matched the selected underwriting years and filters."
)


def _segment_text(row: dict[str, Any], dimensions: list[Dimension]) -> str:
    return ", ".join(
        f"{dimension.value}={row[dimension.value]}" for dimension in dimensions
    )


def _underwriting_year_chart(
    dimensions: list[Dimension],
    y: str,
    title: str,
) -> ChartMetadata:
    """Grouped bars by underwriting year when present, one series per other segment."""
    x = (
        Dimension.UNDERWRITING_YEAR
        if Dimension.UNDERWRITING_YEAR in dimensions
        else dimensions[0]
    )

    return ChartMetadata(
        chart_type=ChartType.GROUPED_BAR,
        x=x.value,
        y=y,
        series=[dimension.value for dimension in dimensions if dimension != x],
        title=title,
    )


def _underwriting_year_response(
    *,
    question: str,
    tool_name: str,
    request: SeverityRequest | ExposureSummaryRequest | PortfolioQualityRequest,
    raw_results: list[dict[str, Any]],
    answer: str,
    chart: ChartMetadata | None,
    definition: str,
    database_path: DataSource,
    dataset_version: str,
) -> AnalyticsResponse:
    return AnalyticsResponse(
        question=question,
        tool_calls=[
            ToolCallAudit(
                tool_name=tool_name,
                validated_arguments=request.model_dump(mode="json"),
                execution_status="success",
            )
        ],
        raw_results=raw_results,
        answer=answer,
        chart=chart,
        audit=AuditMetadata(
            dataset_version=dataset_version,
            calculation_definition=definition,
            database_path=describe_data_source(database_path),
        ),
    )


def build_severity_response(
    question: str,
    request: SeverityRequest,
    raw_results: list[dict[str, Any]],
    database_path: DataSource,
    dataset_version: str,
) -> AnalyticsResponse:
    rows_with_claims = [
        row for row in raw_results if row["average_severity"] is not None
    ]

    if not raw_results:
        answer = NO_ROWS_ANSWER
    elif not rows_with_claims:
        answer = (
            f"The analysis returned {len(raw_results)} segments, but none has a "
            "claim, so average claim severity is not defined."
        )
    else:
        highest = max(rows_with_claims, key=lambda row: row["average_severity"])
        answer = (
            f"The analysis returned {len(raw_results)} segments. "
            f"The highest average claim severity is "
            f"{highest['average_severity']:,.2f} CAD for "
            f"{_segment_text(highest, request.dimensions)}. "
            "Severity is calculated as paid claim amount divided by claim count."
        )

    return _underwriting_year_response(
        question=question,
        tool_name=SEVERITY_TOOL,
        request=request,
        raw_results=raw_results,
        answer=answer,
        chart=_underwriting_year_chart(
            request.dimensions,
            "average_severity",
            "Average claim severity by underwriting year (CAD per claim)",
        ),
        definition=SEVERITY_DEFINITION,
        database_path=database_path,
        dataset_version=dataset_version,
    )


def build_exposure_summary_response(
    question: str,
    request: ExposureSummaryRequest,
    raw_results: list[dict[str, Any]],
    database_path: DataSource,
    dataset_version: str,
) -> AnalyticsResponse:
    if not raw_results:
        answer = NO_ROWS_ANSWER
    else:
        largest = max(raw_results, key=lambda row: row["exposure_units"])
        total_policies = sum(row["policy_count"] for row in raw_results)
        total_exposure = sum(row["exposure_units"] for row in raw_results)
        answer = (
            f"The analysis returned {len(raw_results)} segments covering "
            f"{total_policies:,} policies and {total_exposure:,.2f} exposure units. "
            f"The largest exposure is {largest['exposure_units']:,.2f} units for "
            f"{_segment_text(largest, request.dimensions)}."
        )

    return _underwriting_year_response(
        question=question,
        tool_name=EXPOSURE_SUMMARY_TOOL,
        request=request,
        raw_results=raw_results,
        answer=answer,
        chart=_underwriting_year_chart(
            request.dimensions,
            "exposure_units",
            "Exposure units by underwriting year",
        ),
        definition=EXPOSURE_SUMMARY_DEFINITION,
        database_path=database_path,
        dataset_version=dataset_version,
    )


def _ratio(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator else None


def build_portfolio_quality_response(
    question: str,
    request: PortfolioQualityRequest,
    raw_results: list[dict[str, Any]],
    database_path: DataSource,
    dataset_version: str,
) -> AnalyticsResponse:
    if not raw_results:
        answer = NO_ROWS_ANSWER
    else:

        def total(key: str) -> float:
            return sum(row[key] for row in raw_results)

        metrics = [
            (
                "paid loss ratio",
                _ratio(total("paid_claim_amount"), total("written_premium")),
                "{:.1%}",
            ),
            (
                "claim frequency",
                _ratio(total("claim_count"), total("exposure_units")),
                "{:.3f} claims per exposure unit",
            ),
            (
                "average claim severity",
                _ratio(total("paid_claim_amount"), total("claim_count")),
                "{:,.2f} CAD",
            ),
            (
                "premium per exposure unit",
                _ratio(total("written_premium"), total("exposure_units")),
                "{:,.2f} CAD",
            ),
            (
                "share of policies with a claim",
                _ratio(total("policies_with_claims"), total("policy_count")),
                "{:.1%}",
            ),
        ]
        described = [
            f"{label} {template.format(value)}"
            for label, value, template in metrics
            if value is not None
        ]
        answer = (
            f"The analysis returned {len(raw_results)} segments. "
            f"Across them: {'; '.join(described)}. "
            "Metrics are computed on an underwriting-year basis."
        )

    return _underwriting_year_response(
        question=question,
        tool_name=PORTFOLIO_QUALITY_TOOL,
        request=request,
        raw_results=raw_results,
        answer=answer,
        chart=None,
        definition=PORTFOLIO_QUALITY_DEFINITION,
        database_path=database_path,
        dataset_version=dataset_version,
    )


class UnsupportedToolResponseError(ValueError):
    """Raised when no response builder exists for the selected tool."""


# Arguments are typed Any: ToolSelection guarantees the argument model matches
# the selected tool before its builder is called.
ResponseBuilder = Callable[
    [str, Any, list[dict[str, Any]], DataSource, str],
    AnalyticsResponse,
]

RESPONSE_BUILDERS: dict[str, ResponseBuilder] = {
    LOSS_RATIO_TOOL: build_loss_ratio_response,
    CLAIM_FREQUENCY_TOOL: build_claim_frequency_response,
    SEVERITY_TOOL: build_severity_response,
    EXPOSURE_SUMMARY_TOOL: build_exposure_summary_response,
    PORTFOLIO_QUALITY_TOOL: build_portfolio_quality_response,
}


def build_response(
    question: str,
    selection: ToolSelection,
    raw_results: list[dict[str, Any]],
    database_path: DataSource,
    dataset_version: str,
) -> AnalyticsResponse:
    """Build the response with the builder registered for the selected tool."""
    builder = RESPONSE_BUILDERS.get(selection.tool_name)

    if builder is None:
        raise UnsupportedToolResponseError(
            f"No response builder for tool: {selection.tool_name}"
        )

    return builder(
        question,
        selection.arguments,
        raw_results,
        database_path,
        dataset_version,
    )
