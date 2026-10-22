from __future__ import annotations

from pathlib import Path

from insurance_data_analyst_agent.config import Settings
from insurance_data_analyst_agent.infrastructure.persistence.access import DataSource
from insurance_data_analyst_agent.models.analytics import AnalyticsResponse
from insurance_data_analyst_agent.models.routing import (
    ToolArguments,
    ToolSelection,
    selection_for,
)
from insurance_data_analyst_agent.services.agent import (
    InsuranceDataAnalystAgent,
    QuestionRouter,
)
from insurance_data_analyst_agent.services.audit_writer import AuditWriter
from insurance_data_analyst_agent.tools.registry import (
    build_default_tool_registry,
)


def fixed_router(arguments: ToolArguments) -> QuestionRouter:
    """Return a router that always selects the tool owning the arguments."""
    selection = selection_for(arguments)

    def route(question: str, available_years: list[int]) -> ToolSelection:
        return selection

    return route


def build_agent(
    settings: Settings,
    data_source: DataSource,
    router: QuestionRouter,
) -> InsuranceDataAnalystAgent:
    return InsuranceDataAnalystAgent(
        database_path=data_source,
        dataset_version=settings.dataset_version,
        registry=build_default_tool_registry(),
        audit_writer=AuditWriter(output_directory=settings.audit_directory),
        router=router,
    )


def run_tool_call(
    settings: Settings,
    data_source: DataSource,
    arguments: ToolArguments,
    chart_output_path: Path | None = None,
) -> AnalyticsResponse:
    """Run the tool owning the typed arguments, without any question routing.

    Shared by the REST API and the MCP server so that both transports use the
    same agent, registry, audit writer and response contract.
    """
    tool_name = selection_for(arguments).tool_name
    agent = build_agent(settings, data_source, fixed_router(arguments))
    return agent.answer(
        question=f"Direct call: {tool_name}",
        chart_output_path=chart_output_path,
    )
