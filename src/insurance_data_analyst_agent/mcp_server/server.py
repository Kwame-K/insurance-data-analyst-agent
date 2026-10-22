"""MCP server exposing the five controlled analytical tools over stdio."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any, TypeVar

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ValidationError
from sqlalchemy.exc import OperationalError

from insurance_data_analyst_agent.api.schemas import ApiResponse
from insurance_data_analyst_agent.config import Settings
from insurance_data_analyst_agent.config import settings as default_settings
from insurance_data_analyst_agent.infrastructure.persistence.access import (
    DataSource,
    build_data_source,
)
from insurance_data_analyst_agent.logging_config import (
    configure_logging,
    new_correlation_id,
    set_correlation_id,
)
from insurance_data_analyst_agent.models.analytics import (
    ClaimFrequencyRequest,
    Dimension,
    ExposureSummaryRequest,
    LossRatioRequest,
    PortfolioQualityRequest,
    SeverityRequest,
)
from insurance_data_analyst_agent.models.routing import ToolArguments
from insurance_data_analyst_agent.services.direct_call import run_tool_call

logger = logging.getLogger(__name__)

mcp = MCPServer("insurance-data-analyst-agent")

T = TypeVar("T", bound=BaseModel)

_ANALYTICS_TOOL = ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=False,
)


def get_settings() -> Settings:
    return default_settings


@lru_cache(maxsize=1)
def get_data_source() -> DataSource:
    """Create and cache the configured data source (PostgreSQL or SQLite)."""
    return build_data_source(get_settings())


def _summarize(error: ValidationError) -> str:
    messages = []
    for item in error.errors():
        location = ".".join(str(part) for part in item["loc"])
        messages.append(f"{location}: {item['msg']}" if location else item["msg"])
    return "; ".join(messages)


def _build(model: type[T], values: dict[str, Any]) -> T:
    """Validate tool input with the same Pydantic contract as the REST API."""
    try:
        return model.model_validate(
            {key: value for key, value in values.items() if value is not None}
        )
    except ValidationError as error:
        raise ToolError(f"VALIDATION_ERROR: {_summarize(error)}") from error


def _execute(arguments: ToolArguments) -> dict[str, Any]:
    correlation_id = new_correlation_id()
    set_correlation_id(correlation_id)

    try:
        response = run_tool_call(get_settings(), get_data_source(), arguments)
    except OperationalError as error:
        logger.exception("Data source unavailable")
        raise ToolError("DATA_UNAVAILABLE: Data source is unavailable.") from error
    except Exception as error:
        logger.exception("Unexpected MCP tool error")
        raise ToolError("INTERNAL_ERROR: Internal server error.") from error

    return ApiResponse(
        correlation_id=correlation_id,
        routing_provider="direct",
        data=response,
    ).model_dump(mode="json")


@mcp.tool(annotations=_ANALYTICS_TOOL)
def get_loss_ratio_by_segment(
    underwriting_years: list[int],
    dimensions: list[Dimension] | None = None,
    provinces: list[str] | None = None,
    lines_of_business: list[str] | None = None,
) -> dict[str, Any]:
    """Paid loss ratio (paid claims / written premium) by segment.

    Cohort basis: claims of the policies underwritten in the selected years.
    Segments are province, line_of_business and underwriting_year. Provinces
    are QC, ON, BC and AB. Paid basis only: not earned premium, not incurred.
    """
    return _execute(
        _build(
            LossRatioRequest,
            {
                "underwriting_years": underwriting_years,
                "dimensions": dimensions,
                "provinces": provinces,
                "lines_of_business": lines_of_business,
            },
        )
    )


@mcp.tool(annotations=_ANALYTICS_TOOL)
def get_claim_frequency_trend(
    years: list[int],
    dimensions: list[Dimension] | None = None,
    provinces: list[str] | None = None,
    lines_of_business: list[str] | None = None,
) -> dict[str, Any]:
    """Claim frequency (claims per exposure unit) and year-over-year change.

    Calendar-year basis; at least two years are required. Not comparable with
    the cohort claim_frequency of get_portfolio_quality_metrics.
    """
    return _execute(
        _build(
            ClaimFrequencyRequest,
            {
                "years": years,
                "dimensions": dimensions,
                "provinces": provinces,
                "lines_of_business": lines_of_business,
            },
        )
    )


@mcp.tool(annotations=_ANALYTICS_TOOL)
def get_claim_severity(
    underwriting_years: list[int],
    dimensions: list[Dimension] | None = None,
    provinces: list[str] | None = None,
    lines_of_business: list[str] | None = None,
) -> dict[str, Any]:
    """Average paid amount per claim by segment (underwriting-year cohort)."""
    return _execute(
        _build(
            SeverityRequest,
            {
                "underwriting_years": underwriting_years,
                "dimensions": dimensions,
                "provinces": provinces,
                "lines_of_business": lines_of_business,
            },
        )
    )


@mcp.tool(annotations=_ANALYTICS_TOOL)
def get_exposure_summary(
    underwriting_years: list[int],
    dimensions: list[Dimension] | None = None,
    provinces: list[str] | None = None,
    lines_of_business: list[str] | None = None,
) -> dict[str, Any]:
    """Policy count, exposure units, written premium and average exposure per policy."""
    return _execute(
        _build(
            ExposureSummaryRequest,
            {
                "underwriting_years": underwriting_years,
                "dimensions": dimensions,
                "provinces": provinces,
                "lines_of_business": lines_of_business,
            },
        )
    )


@mcp.tool(annotations=_ANALYTICS_TOOL)
def get_portfolio_quality_metrics(
    underwriting_years: list[int],
    dimensions: list[Dimension] | None = None,
    provinces: list[str] | None = None,
    lines_of_business: list[str] | None = None,
) -> dict[str, Any]:
    """Loss ratio, claim frequency, severity, premium per exposure unit and claim share.

    All metrics use the underwriting-year cohort basis. The tool returns metrics,
    never decisions, thresholds or alerts.
    """
    return _execute(
        _build(
            PortfolioQualityRequest,
            {
                "underwriting_years": underwriting_years,
                "dimensions": dimensions,
                "provinces": provinces,
                "lines_of_business": lines_of_business,
            },
        )
    )


def main() -> None:
    """Start the MCP server using the stdio transport."""
    configure_logging(get_settings().log_level)
    mcp.run()


if __name__ == "__main__":
    main()
