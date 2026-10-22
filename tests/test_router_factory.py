from __future__ import annotations

import pytest

from insurance_data_analyst_agent.config import Settings
from insurance_data_analyst_agent.services.llm_router import LLMRouter
from insurance_data_analyst_agent.services.router import route_question
from insurance_data_analyst_agent.services.router_factory import (
    build_api_router,
    build_llm_providers,
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("GEMINI_API_KEY", "GEMINI_MODEL", "GROQ_API_KEY", "GROQ_MODEL"):
        monkeypatch.delenv(name, raising=False)


def make_settings(**values: str) -> Settings:
    return Settings(_env_file=None, **values)  # type: ignore[call-arg, arg-type]


def test_no_keys_uses_deterministic_router() -> None:
    assert build_api_router(make_settings()) is route_question


def test_providers_are_ordered_gemini_then_groq() -> None:
    settings = make_settings(
        gemini_api_key="g", gemini_model="gm", groq_api_key="q", groq_model="qm"
    )

    assert [name for name, _ in build_llm_providers(settings)] == ["gemini", "groq"]
    assert isinstance(build_api_router(settings), LLMRouter)


def test_provider_without_model_is_skipped() -> None:
    settings = make_settings(gemini_api_key="g", groq_api_key="q", groq_model="qm")

    assert [name for name, _ in build_llm_providers(settings)] == ["groq"]
