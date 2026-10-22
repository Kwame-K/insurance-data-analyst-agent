from __future__ import annotations

from typing import Final

import pytest
from pydantic import ValidationError

from insurance_data_analyst_agent.models.analytics import (
    ClaimFrequencyRequest,
    LossRatioRequest,
)
from insurance_data_analyst_agent.models.routing import ToolSelection

LOSS_RATIO: Final = "get_loss_ratio_by_segment"
CLAIM_FREQUENCY: Final = "get_claim_frequency_trend"


def claim_frequency_selection() -> ToolSelection:
    return ToolSelection(
        tool_name=CLAIM_FREQUENCY,
        arguments=ClaimFrequencyRequest(years=[2024, 2025]),
    )


def test_loss_ratio_payload_uses_loss_ratio_model() -> None:
    selection = ToolSelection.model_validate(
        {"tool_name": LOSS_RATIO, "arguments": {"underwriting_years": [2025]}}
    )

    assert isinstance(selection.arguments, LossRatioRequest)


def test_claim_frequency_payload_uses_claim_frequency_model() -> None:
    selection = ToolSelection.model_validate(
        {"tool_name": CLAIM_FREQUENCY, "arguments": {"years": [2024, 2025]}}
    )

    assert isinstance(selection.arguments, ClaimFrequencyRequest)


def test_arguments_of_the_other_tool_are_rejected() -> None:
    with pytest.raises(ValidationError):
        ToolSelection.model_validate(
            {"tool_name": CLAIM_FREQUENCY, "arguments": {"underwriting_years": [2025]}}
        )

    with pytest.raises(ValidationError):
        ToolSelection.model_validate(
            {"tool_name": LOSS_RATIO, "arguments": {"years": [2024, 2025]}}
        )


def test_mismatched_argument_instance_is_rejected() -> None:
    with pytest.raises(ValidationError, match="do not match tool"):
        ToolSelection(
            tool_name=LOSS_RATIO,
            arguments=ClaimFrequencyRequest(years=[2024, 2025]),
        )


def test_unknown_tool_and_extra_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        ToolSelection.model_validate(
            {"tool_name": "drop_table", "arguments": {"years": [2024, 2025]}}
        )

    with pytest.raises(ValidationError):
        ToolSelection.model_validate(
            {
                "tool_name": LOSS_RATIO,
                "arguments": {"underwriting_years": [2025]},
                "sql": "SELECT 1",
            }
        )


def test_every_tool_has_exactly_one_argument_model() -> None:
    from insurance_data_analyst_agent.models.routing import (
        ARGUMENT_MODELS,
        TOOL_NAME_BY_ARGUMENTS,
    )

    assert {name: model for model, name in TOOL_NAME_BY_ARGUMENTS.items()} == (
        ARGUMENT_MODELS
    )
