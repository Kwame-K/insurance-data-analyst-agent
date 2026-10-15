from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from insurance_data_analyst_agent.charts import generate_chart
from insurance_data_analyst_agent.database import (
    get_available_underwriting_years,
)
from insurance_data_analyst_agent.models.analytics import (
    AnalyticsResponse,
    ToolCallAudit,
)
from insurance_data_analyst_agent.models.audit import (
    AgentRunAudit,
    ErrorAudit,
)
from insurance_data_analyst_agent.models.routing import (
    ToolSelection,
)
from insurance_data_analyst_agent.services.audit_writer import (
    AuditWriter,
)
from insurance_data_analyst_agent.services.response_builder import (
    build_loss_ratio_response,
)
from insurance_data_analyst_agent.services.router import (
    route_question,
)
from insurance_data_analyst_agent.tools.registry import (
    ToolRegistry,
)

QuestionRouter = Callable[
    [str, list[int]],
    ToolSelection,
]


@dataclass(frozen=True)
class InsuranceDataAnalystAgent:
    """Controlled and deterministic insurance portfolio analytics agent."""

    database_path: Path
    dataset_version: str
    registry: ToolRegistry
    audit_writer: AuditWriter
    router: QuestionRouter = route_question
    agent_version: str = "0.1.0"

    def answer(
        self,
        question: str,
        chart_output_path: Path | None = None,
    ) -> AnalyticsResponse:
        """Route, execute, audit, and return one analytical response."""
        tool_calls: list[ToolCallAudit] = []
        raw_results: list[dict] = []

        try:
            available_years = get_available_underwriting_years(self.database_path)

            tool_selection = self.router(
                question,
                available_years,
            )

            tool_call = ToolCallAudit(
                tool_name=tool_selection.tool_name,
                validated_arguments=tool_selection.arguments.model_dump(mode="json"),
                execution_status="failed",
            )

            tool_calls.append(tool_call)

            raw_results = self.registry.execute(
                selection=tool_selection,
                database_path=self.database_path,
            )

            tool_call.execution_status = "success"

            response = build_loss_ratio_response(
                question=question,
                request=tool_selection.arguments,
                raw_results=raw_results,
                database_path=self.database_path,
                dataset_version=self.dataset_version,
            )

            if (
                chart_output_path is not None
                and response.chart is not None
                and raw_results
            ):
                generated_chart_path = generate_chart(
                    raw_results=raw_results,
                    metadata=response.chart,
                    output_path=chart_output_path,
                )

                response.chart.output_path = str(generated_chart_path)

            self.audit_writer.write(
                AgentRunAudit(
                    agent_version=self.agent_version,
                    dataset_version=self.dataset_version,
                    database_path=str(self.database_path),
                    question=question,
                    status="success",
                    tool_calls=tool_calls,
                    raw_results=raw_results,
                    final_response=response,
                )
            )

            return response

        except Exception as error:
            self.audit_writer.write(
                AgentRunAudit(
                    agent_version=self.agent_version,
                    dataset_version=self.dataset_version,
                    database_path=str(self.database_path),
                    question=question,
                    status="failed",
                    tool_calls=tool_calls,
                    raw_results=raw_results,
                    error=ErrorAudit(
                        error_type=type(error).__name__,
                        message=str(error),
                    ),
                )
            )

            raise
