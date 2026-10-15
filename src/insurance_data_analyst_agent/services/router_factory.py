from __future__ import annotations

import logging

from insurance_data_analyst_agent.config import Settings
from insurance_data_analyst_agent.llm.base import LLMClient
from insurance_data_analyst_agent.llm.fallback import FallbackLLMClient
from insurance_data_analyst_agent.llm.gemini_client import GeminiLLMClient
from insurance_data_analyst_agent.llm.groq_client import GroqLLMClient
from insurance_data_analyst_agent.services.agent import QuestionRouter
from insurance_data_analyst_agent.services.llm_router import LLMRouter
from insurance_data_analyst_agent.services.router import route_question

logger = logging.getLogger(__name__)


def build_llm_providers(settings: Settings) -> list[tuple[str, LLMClient]]:
    """Return configured providers in priority order: Gemini, then Groq."""
    providers: list[tuple[str, LLMClient]] = []

    if settings.gemini_api_key and settings.gemini_model:
        providers.append(
            (
                "gemini",
                GeminiLLMClient(
                    api_key=settings.gemini_api_key.get_secret_value(),
                    model=settings.gemini_model,
                ),
            )
        )

    if settings.groq_api_key and settings.groq_model:
        providers.append(
            (
                "groq",
                GroqLLMClient(
                    api_key=settings.groq_api_key.get_secret_value(),
                    model=settings.groq_model,
                ),
            )
        )

    return providers


def build_api_router(settings: Settings) -> QuestionRouter:
    """Build the API router: LLM chain when configured, else deterministic."""
    providers = build_llm_providers(settings)

    if not providers:
        logger.warning("No LLM provider configured; using deterministic router.")
        return route_question

    logger.info(
        "LLM providers configured: %s",
        ", ".join(name for name, _ in providers),
    )

    return LLMRouter(client=FallbackLLMClient(providers=providers))
