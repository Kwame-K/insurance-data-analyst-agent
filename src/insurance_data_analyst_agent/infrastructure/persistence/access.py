from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Connection, Engine

from insurance_data_analyst_agent.config import Settings
from insurance_data_analyst_agent.infrastructure.persistence.database import (
    create_database_engine,
)

DataSource = Path | Engine


def build_data_source(settings: Settings) -> DataSource:
    """Use PostgreSQL when DATABASE_URL is set, otherwise local SQLite."""
    if settings.database_url:
        return create_database_engine(
            settings.database_url,
            echo=settings.database_echo,
        )
    return settings.database_path


def describe_data_source(source: DataSource) -> str:
    """Return a safe description: never a URL, user or password."""
    if isinstance(source, Engine):
        return f"{source.url.get_backend_name()}:{source.url.database}"
    return str(source)


@contextmanager
def connect(source: DataSource) -> Iterator[Connection]:
    """Yield a connection for an Engine or a SQLite file path."""
    if isinstance(source, Engine):
        with source.connect() as connection:
            yield connection
        return

    if not source.exists():
        raise FileNotFoundError(f"Database does not exist: {source}")

    engine = create_database_engine(f"sqlite:///{source}")
    try:
        with engine.connect() as connection:
            yield connection
    finally:
        engine.dispose()
