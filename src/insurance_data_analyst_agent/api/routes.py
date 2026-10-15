from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Request

from insurance_data_analyst_agent.api.schemas import (
    AnalyzeRequest,
    ApiResponse,
    HealthResponse,
    LossRatioApiRequest,
)
from insurance_data_analyst_agent.config import Settings
from insurance_data_analyst_agent.llm.trace import routing_provider_var
from insurance_data_analyst_agent.models.analytics import LossRatioRequest
from insurance_data_analyst_agent.models.routing import ToolSelection
from insurance_data_analyst_agent.services.agent import (
    InsuranceDataAnalystAgent,
    QuestionRouter,
)
from insurance_data_analyst_agent.services.audit_writer import AuditWriter
from insurance_data_analyst_agent.tools.registry import (
    build_default_tool_registry,
)

logger = logging.getLogger(__name__)

health_router = APIRouter(tags=["health"])
v1_router = APIRouter(prefix="/v1", tags=["analytics"])


def fixed_router(arguments: LossRatioRequest) -> QuestionRouter:
    """Return a router that always selects the loss-ratio tool."""
    selection = ToolSelection(
        tool_name="get_loss_ratio_by_segment",
        arguments=arguments,
    )

    def route(question: str, available_years: list[int]) -> ToolSelection:
        return selection

    return route


def build_agent(
    settings: Settings,
    router: QuestionRouter,
) -> InsuranceDataAnalystAgent:
    return InsuranceDataAnalystAgent(
        database_path=settings.database_path,
        dataset_version=settings.dataset_version,
        registry=build_default_tool_registry(),
        audit_writer=AuditWriter(output_directory=settings.audit_directory),
        router=router,
    )


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

    agent = build_agent(settings, request.app.state.router)
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


@v1_router.post("/loss-ratio", response_model=ApiResponse)
def loss_ratio(payload: LossRatioApiRequest, request: Request) -> ApiResponse:
    settings: Settings = request.app.state.settings
    correlation_id: str = request.state.correlation_id
    request_id = bind_request_id(request, payload.request_id)

    agent = build_agent(settings, fixed_router(payload.arguments))
    response = agent.answer(
        question="Direct call: get_loss_ratio_by_segment",
        chart_output_path=chart_path_for(
            settings, correlation_id, payload.include_chart
        ),
    )

    logger.info("loss-ratio direct call completed")

    return ApiResponse(
        correlation_id=correlation_id,
        request_id=request_id,
        routing_provider="direct",
        data=response,
    )
