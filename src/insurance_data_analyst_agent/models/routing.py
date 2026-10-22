from __future__ import annotations

from typing import Any, Final, Literal, Self

from pydantic import BaseModel, ConfigDict, model_validator

from insurance_data_analyst_agent.models.analytics import (
    ClaimFrequencyRequest,
    ExposureSummaryRequest,
    LossRatioRequest,
    PortfolioQualityRequest,
    SeverityRequest,
)

LOSS_RATIO_TOOL: Final = "get_loss_ratio_by_segment"
CLAIM_FREQUENCY_TOOL: Final = "get_claim_frequency_trend"
SEVERITY_TOOL: Final = "get_claim_severity"
EXPOSURE_SUMMARY_TOOL: Final = "get_exposure_summary"
PORTFOLIO_QUALITY_TOOL: Final = "get_portfolio_quality_metrics"

ToolName = Literal[
    "get_loss_ratio_by_segment",
    "get_claim_frequency_trend",
    "get_claim_severity",
    "get_exposure_summary",
    "get_portfolio_quality_metrics",
]
ToolArguments = (
    LossRatioRequest
    | ClaimFrequencyRequest
    | SeverityRequest
    | ExposureSummaryRequest
    | PortfolioQualityRequest
)

ARGUMENT_MODELS: dict[str, type[BaseModel]] = {
    LOSS_RATIO_TOOL: LossRatioRequest,
    CLAIM_FREQUENCY_TOOL: ClaimFrequencyRequest,
    SEVERITY_TOOL: SeverityRequest,
    EXPOSURE_SUMMARY_TOOL: ExposureSummaryRequest,
    PORTFOLIO_QUALITY_TOOL: PortfolioQualityRequest,
}


TOOL_NAME_BY_ARGUMENTS: dict[type[BaseModel], ToolName] = {
    LossRatioRequest: LOSS_RATIO_TOOL,
    ClaimFrequencyRequest: CLAIM_FREQUENCY_TOOL,
    SeverityRequest: SEVERITY_TOOL,
    ExposureSummaryRequest: EXPOSURE_SUMMARY_TOOL,
    PortfolioQualityRequest: PORTFOLIO_QUALITY_TOOL,
}


class ToolSelection(BaseModel):
    """A validated request to execute one allowed analytical tool."""

    model_config = ConfigDict(extra="forbid")

    tool_name: ToolName
    arguments: ToolArguments

    @model_validator(mode="before")
    @classmethod
    def _parse_arguments_for_tool(cls, data: Any) -> Any:
        """Validate raw arguments with the model of the selected tool only."""
        if not isinstance(data, dict):
            return data

        arguments = data.get("arguments")
        model = ARGUMENT_MODELS.get(data.get("tool_name", ""))

        if model is not None and isinstance(arguments, dict):
            return {**data, "arguments": model.model_validate(arguments)}

        return data

    @model_validator(mode="after")
    def _check_arguments_match_tool(self) -> Self:
        if type(self.arguments) is not ARGUMENT_MODELS[self.tool_name]:
            raise ValueError(f"Arguments do not match tool: {self.tool_name}.")

        return self


def selection_for(arguments: ToolArguments) -> ToolSelection:
    """Build the selection of the tool that owns this argument model."""
    return ToolSelection(
        tool_name=TOOL_NAME_BY_ARGUMENTS[type(arguments)],
        arguments=arguments,
    )
