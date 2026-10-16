from __future__ import annotations

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
    LossRatioRequest,
    ToolCallAudit,
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
