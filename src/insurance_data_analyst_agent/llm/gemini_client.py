from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from google import genai
from google.genai import types

from insurance_data_analyst_agent.llm.base import (
    LLMClientError,
)

REQUEST_TIMEOUT_MS = 10_000


@dataclass
class GeminiLLMClient:
    """Gemini implementation of the provider-agnostic LLMClient protocol."""

    api_key: str
    model: str
    client: Any = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self.client is None:
            self.client = genai.Client(
                api_key=self.api_key,
                http_options=types.HttpOptions(timeout=REQUEST_TIMEOUT_MS),
            )

    def generate_tool_selection(
        self,
        *,
        system_prompt: str,
        user_question: str,
    ) -> dict[str, Any]:
        """Request a JSON-compatible tool-selection candidate from Gemini."""
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=user_question,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_mime_type="application/json",
                    temperature=0,
                ),
            )
        except Exception as error:
            raise LLMClientError(f"Gemini request failed: {error}") from error

        content = response.text

        if not content:
            raise LLMClientError("Gemini returned an empty response.")

        try:
            payload = json.loads(content)
        except json.JSONDecodeError as error:
            raise LLMClientError("Gemini returned invalid JSON.") from error

        if not isinstance(payload, dict):
            raise LLMClientError("Gemini response must be a JSON object.")

        return payload
