from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import Engine

from insurance_data_analyst_agent.api.errors import register_exception_handlers
from insurance_data_analyst_agent.api.middleware import correlation_middleware
from insurance_data_analyst_agent.api.routes import health_router, v1_router
from insurance_data_analyst_agent.config import Settings
from insurance_data_analyst_agent.config import settings as default_settings
from insurance_data_analyst_agent.infrastructure.persistence.access import (
    DataSource,
    build_data_source,
)
from insurance_data_analyst_agent.services.agent import (
    InsuranceDataAnalystAgent,
    QuestionRouter,
)
from insurance_data_analyst_agent.services.router_factory import (
    build_api_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    data_source = app.state.data_source
    if isinstance(data_source, Engine):
        data_source.dispose()


def create_app(
    settings: Settings | None = None,
    router: QuestionRouter | None = None,
    data_source: DataSource | None = None,
) -> FastAPI:
    """Application factory: settings, router and data source can be injected."""
    resolved_settings = settings or default_settings

    app = FastAPI(
        title="Insurance Data Analyst Agent",
        version=InsuranceDataAnalystAgent.agent_version,
        description="Controlled and auditable insurance portfolio analytics.",
        lifespan=lifespan,
    )

    app.state.settings = resolved_settings
    app.state.router = router or build_api_router(resolved_settings)
    app.state.data_source = data_source or build_data_source(resolved_settings)

    app.middleware("http")(correlation_middleware)
    register_exception_handlers(app)
    app.include_router(health_router)
    app.include_router(v1_router)

    return app
