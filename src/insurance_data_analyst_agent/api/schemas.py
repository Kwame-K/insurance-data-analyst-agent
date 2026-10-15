from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from insurance_data_analyst_agent.models.analytics import (
    AnalyticsResponse,
    Dimension,
    LossRatioRequest,
)

API_VERSION = "v1"

RequestId = Field(
    default=None,
    min_length=1,
    max_length=128,
    pattern=r"^[A-Za-z0-9._:-]+$",
    description="Identifier supplied by the consumer, echoed back as is.",
)

CHART_DIMENSIONS = {
    Dimension.PROVINCE,
    Dimension.LINE_OF_BUSINESS,
    Dimension.UNDERWRITING_YEAR,
}


class AnalyzeRequest(BaseModel):
    """Natural-language question sent to POST /v1/analyze."""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=3, max_length=500)
    request_id: str | None = RequestId
    include_chart: bool = False


class LossRatioApiRequest(BaseModel):
    """Typed direct call sent to POST /v1/loss-ratio."""

    model_config = ConfigDict(extra="forbid")

    arguments: LossRatioRequest
    request_id: str | None = RequestId
    include_chart: bool = False

    @model_validator(mode="after")
    def validate_chart_dimensions(self) -> LossRatioApiRequest:
        if self.include_chart and set(self.arguments.dimensions) != CHART_DIMENSIONS:
            raise ValueError(
                "include_chart requires dimensions: province, "
                "line_of_business and underwriting_year."
            )
        return self


class ApiResponse(BaseModel):
    """Versioned success envelope shared by the analytical endpoints."""

    api_version: Literal["v1"] = API_VERSION
    correlation_id: str
    request_id: str | None = None
    status: Literal["success"] = "success"
    routing_provider: str
    data: AnalyticsResponse


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: list[dict[str, Any]] | None = None


class ErrorResponse(BaseModel):
    """Versioned error envelope returned for every failure."""

    api_version: Literal["v1"] = API_VERSION
    correlation_id: str
    request_id: str | None = None
    status: Literal["error"] = "error"
    error: ErrorDetail


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    api_version: Literal["v1"] = API_VERSION
    agent_version: str
