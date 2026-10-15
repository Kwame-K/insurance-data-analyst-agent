from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from insurance_data_analyst_agent.llm.base import (
    LLMClient,
    LLMClientError,
)
from insurance_data_analyst_agent.llm.trace import routing_provider_var

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FallbackLLMClient:
    """Try LLM providers in order and return the first valid JSON object."""

    providers: Sequence[tuple[str, LLMClient]]

    def generate_tool_selection(
        self,
        *,
        system_prompt: str,
        user_question: str,
    ) -> dict[str, Any]:
        errors: list[str] = []

        for name, client in self.providers:
            try:
                result = client.generate_tool_selection(
                    system_prompt=system_prompt,
                    user_question=user_question,
                )
            except LLMClientError as error:
                logger.warning("LLM provider %s failed: %s", name, error)
                errors.append(f"{name}: {error}")
                continue

            routing_provider_var.set(name)
            return result

        raise LLMClientError(
            "No LLM provider succeeded. " + "; ".join(errors)
            if errors
            else "No LLM provider is configured."
        )
