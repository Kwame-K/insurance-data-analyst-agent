from __future__ import annotations

import logging
from dataclasses import dataclass

from pydantic import ValidationError

from insurance_data_analyst_agent.llm.base import (
    LLMClient,
    LLMClientError,
)
from insurance_data_analyst_agent.llm.prompts import (
    TOOL_SELECTION_SYSTEM_PROMPT,
)
from insurance_data_analyst_agent.llm.trace import routing_provider_var
from insurance_data_analyst_agent.models.analytics import (
    ClaimFrequencyRequest,
    Dimension,
    LossRatioRequest,
)
from insurance_data_analyst_agent.models.routing import (
    ToolSelection,
)
from insurance_data_analyst_agent.services.router import (
    check_unsupported_scope,
    normalize_text,
    route_question,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LLMRouter:
    """LLM-assisted router with deterministic fallback."""

    client: LLMClient

    def __call__(
        self,
        question: str,
        available_years: list[int],
    ) -> ToolSelection:
        """Return LLM selection when valid, otherwise use fallback routing."""
        routing_provider_var.set("deterministic")

        try:
            raw_selection = self.client.generate_tool_selection(
                system_prompt=TOOL_SELECTION_SYSTEM_PROMPT,
                user_question=question,
            )

            selection = ToolSelection.model_validate(raw_selection)

            self._validate_selection_against_dataset(
                selection=selection,
                available_years=available_years,
            )

            if not isinstance(selection.arguments, LossRatioRequest):
                check_unsupported_scope(normalize_text(question))

            return selection

        except (
            LLMClientError,
            ValidationError,
            ValueError,
            TypeError,
        ) as error:
            logger.warning(
                "LLM routing failed, using deterministic fallback: %s",
                error,
            )
            routing_provider_var.set("deterministic")

            return route_question(
                question=question,
                available_years=available_years,
            )

    @staticmethod
    def _validate_selection_against_dataset(
        selection: ToolSelection,
        available_years: list[int],
    ) -> None:
        """Validate LLM-selected arguments against local data constraints."""
        arguments = selection.arguments

        if isinstance(arguments, ClaimFrequencyRequest):
            unavailable = [
                year for year in arguments.years if year not in available_years
            ]

            if unavailable:
                unavailable_text = ", ".join(str(year) for year in unavailable)
                raise ValueError(f"LLM selected unavailable years: {unavailable_text}.")

            return

        unavailable_years = [
            year for year in arguments.underwriting_years if year not in available_years
        ]

        if unavailable_years:
            unavailable_years_text = ", ".join(str(year) for year in unavailable_years)
            raise ValueError(
                "LLM selected unavailable underwriting years: "
                f"{unavailable_years_text}."
            )

        if not isinstance(arguments, LossRatioRequest):
            return

        expected_dimensions = [
            Dimension.PROVINCE,
            Dimension.LINE_OF_BUSINESS,
            Dimension.UNDERWRITING_YEAR,
        ]

        if arguments.dimensions != expected_dimensions:
            raise ValueError("LLM selected unsupported loss-ratio dimensions.")
