from __future__ import annotations

from fastapi import FastAPI

from insurance_data_analyst_agent.api.errors import register_exception_handlers
from insurance_data_analyst_agent.api.middleware import correlation_middleware
from insurance_data_analyst_agent.api.routes import health_router, v1_router
from insurance_data_analyst_agent.config import Settings
from insurance_data_analyst_agent.config import settings as default_settings
from insurance_data_analyst_agent.services.agent import (
    InsuranceDataAnalystAgent,
    QuestionRouter,
)
from insurance_data_analyst_agent.services.router_factory import (
    build_api_router,
)


def create_app(
    settings: Settings | None = None,
    router: QuestionRouter | None = None,
) -> FastAPI:
    """Application factory: settings and router can be injected for tests."""
    resolved_settings = settings or default_settings

    app = FastAPI(
        title="Insurance Data Analyst Agent",
        version=InsuranceDataAnalystAgent.agent_version,
        description="Controlled and auditable insurance portfolio analytics.",
    )

    app.state.settings = resolved_settings
    app.state.router = router or build_api_router(resolved_settings)

    app.middleware("http")(correlation_middleware)
    register_exception_handlers(app)
    app.include_router(health_router)
    app.include_router(v1_router)

    return app
