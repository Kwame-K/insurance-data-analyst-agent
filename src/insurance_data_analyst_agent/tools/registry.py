from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from insurance_data_analyst_agent.infrastructure.persistence.access import DataSource
from insurance_data_analyst_agent.models.routing import ToolSelection
from insurance_data_analyst_agent.tools.claim_frequency import (
    get_claim_frequency_trend,
)
from insurance_data_analyst_agent.tools.exposure_summary import (
    get_exposure_summary,
)
from insurance_data_analyst_agent.tools.loss_ratio import (
    get_loss_ratio_by_segment,
)
from insurance_data_analyst_agent.tools.portfolio_quality import (
    get_portfolio_quality_metrics,
)
from insurance_data_analyst_agent.tools.severity import get_claim_severity

# Arguments are typed Any: ToolSelection guarantees the argument model matches
# the selected tool before the registry executes a handler.
ToolHandler = Callable[
    [DataSource, Any],
    list[dict[str, Any]],
]


class ToolNotFoundError(ValueError):
    """Raised when a tool is not registered in the tool registry."""


@dataclass(frozen=True)
class RegisteredTool:
    """Definition of one explicitly authorized analytical tool."""

    name: str
    description: str
    handler: ToolHandler


class ToolRegistry:
    """Registry of allowed analytical tools."""

    def __init__(self) -> None:
        self._tools: dict[str, RegisteredTool] = {}

    def register(self, tool: RegisteredTool) -> None:
        """Register one tool and reject duplicate tool names."""
        if tool.name in self._tools:
            raise ValueError(f"Tool is already registered: {tool.name}")

        self._tools[tool.name] = tool

    def get(self, tool_name: str) -> RegisteredTool:
        """Return one registered tool by name."""
        try:
            return self._tools[tool_name]
        except KeyError as error:
            raise ToolNotFoundError(f"Tool is not registered: {tool_name}") from error

    def list_tool_names(self) -> list[str]:
        """Return registered tool names in deterministic order."""
        return sorted(self._tools)

    def execute(
        self,
        selection: ToolSelection,
        database_path: DataSource,
    ) -> list[dict[str, Any]]:
        """Execute the handler associated with a validated selection."""
        tool = self.get(selection.tool_name)

        return tool.handler(
            database_path,
            selection.arguments,
        )


def build_default_tool_registry() -> ToolRegistry:
    """Build the registry containing all tools authorized so far."""
    registry = ToolRegistry()

    registry.register(
        RegisteredTool(
            name="get_loss_ratio_by_segment",
            description=(
                "Calculate paid loss ratio by province, line of business, "
                "and underwriting year."
            ),
            handler=get_loss_ratio_by_segment,
        )
    )

    registry.register(
        RegisteredTool(
            name="get_claim_frequency_trend",
            description=(
                "Calculate claim frequency (claims per exposure unit) "
                "and its year-over-year change, optionally by province "
                "and line of business."
            ),
            handler=get_claim_frequency_trend,
        )
    )

    registry.register(
        RegisteredTool(
            name="get_claim_severity",
            description=(
                "Calculate average claim severity (paid amount per claim) "
                "by underwriting year, province, and line of business."
            ),
            handler=get_claim_severity,
        )
    )

    registry.register(
        RegisteredTool(
            name="get_exposure_summary",
            description=(
                "Summarize policy count, exposure units, and written premium "
                "by underwriting year, province, and line of business."
            ),
            handler=get_exposure_summary,
        )
    )

    registry.register(
        RegisteredTool(
            name="get_portfolio_quality_metrics",
            description=(
                "Calculate loss ratio, claim frequency, average severity, "
                "premium per exposure unit, and share of policies with claims "
                "by underwriting year, province, and line of business."
            ),
            handler=get_portfolio_quality_metrics,
        )
    )

    return registry
