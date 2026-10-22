from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Request

from insurance_data_analyst_agent.api.schemas import (
    AnalyzeRequest,
    ApiResponse,
    ClaimFrequencyApiRequest,
    ExposureSummaryApiRequest,
    HealthResponse,
    LossRatioApiRequest,
    PortfolioQualityApiRequest,
    SeverityApiRequest,
)
from insurance_data_analyst_agent.config import Settings
from insurance_data_analyst_agent.llm.trace import routing_provider_var
from insurance_data_analyst_agent.models.routing import (
    ToolArguments,
    selection_for,
)
from insurance_data_analyst_agent.services.agent import (
    InsuranceDataAnalystAgent,
)
from insurance_data_analyst_agent.services.direct_call import (
    build_agent,
    run_tool_call,
)

logger = logging.getLogger(__name__)

health_router = APIRouter(tags=["health"])
v1_router = APIRouter(prefix="/v1", tags=["analytics"])


def chart_path_for(
    settings: Settings,
    correlation_id: str,
    include_chart: bool,
) -> Path | None:
    if not include_chart:
        return None
    return settings.chart_directory / f"{correlation_id}.png"


def bind_request_id(request: Request, body_request_id: str | None) -> str | None:
    """The body request_id wins over the X-Request-ID header."""
    if body_request_id is not None:
        request.state.request_id = body_request_id
    return request.state.request_id


@health_router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(agent_version=InsuranceDataAnalystAgent.agent_version)


@v1_router.post("/analyze", response_model=ApiResponse)
def analyze(payload: AnalyzeRequest, request: Request) -> ApiResponse:
    settings: Settings = request.app.state.settings
    correlation_id: str = request.state.correlation_id
    request_id = bind_request_id(request, payload.request_id)

    routing_provider_var.set("deterministic")

    agent = build_agent(
        settings, request.app.state.data_source, request.app.state.router
    )
    response = agent.answer(
        question=payload.question,
        chart_output_path=chart_path_for(
            settings, correlation_id, payload.include_chart
        ),
    )

    logger.info("analyze completed via %s", routing_provider_var.get())

    return ApiResponse(
        correlation_id=correlation_id,
        request_id=request_id,
        routing_provider=routing_provider_var.get(),
        data=response,
    )


def run_direct_call(
    request: Request,
    *,
    body_request_id: str | None,
    arguments: ToolArguments,
    include_chart: bool,
) -> ApiResponse:
    """Run the tool owning the typed arguments, without any question routing."""
    settings: Settings = request.app.state.settings
    correlation_id: str = request.state.correlation_id
    request_id = bind_request_id(request, body_request_id)
    tool_name = selection_for(arguments).tool_name

    response = run_tool_call(
        settings,
        request.app.state.data_source,
        arguments,
        chart_output_path=chart_path_for(settings, correlation_id, include_chart),
    )

    logger.info("%s direct call completed", tool_name)

    return ApiResponse(
        correlation_id=correlation_id,
        request_id=request_id,
        routing_provider="direct",
        data=response,
    )


@v1_router.post("/loss-ratio", response_model=ApiResponse)
def loss_ratio(payload: LossRatioApiRequest, request: Request) -> ApiResponse:
    return run_direct_call(
        request,
        body_request_id=payload.request_id,
        arguments=payload.arguments,
        include_chart=payload.include_chart,
    )


@v1_router.post("/claim-frequency", response_model=ApiResponse)
def claim_frequency(payload: ClaimFrequencyApiRequest, request: Request) -> ApiResponse:
    return run_direct_call(
        request,
        body_request_id=payload.request_id,
        arguments=payload.arguments,
        include_chart=payload.include_chart,
    )


@v1_router.post("/severity", response_model=ApiResponse)
def severity(payload: SeverityApiRequest, request: Request) -> ApiResponse:
    return run_direct_call(
        request,
        body_request_id=payload.request_id,
        arguments=payload.arguments,
        include_chart=payload.include_chart,
    )


@v1_router.post("/exposure-summary", response_model=ApiResponse)
def exposure_summary(
    payload: ExposureSummaryApiRequest, request: Request
) -> ApiResponse:
    return run_direct_call(
        request,
        body_request_id=payload.request_id,
        arguments=payload.arguments,
        include_chart=payload.include_chart,
    )


@v1_router.post("/portfolio-quality-metrics", response_model=ApiResponse)
def portfolio_quality_metrics(
    payload: PortfolioQualityApiRequest, request: Request
) -> ApiResponse:
    return run_direct_call(
        request,
        body_request_id=payload.request_id,
        arguments=payload.arguments,
        include_chart=False,
    )
