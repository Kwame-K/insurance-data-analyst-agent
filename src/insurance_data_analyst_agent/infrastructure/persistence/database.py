from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from insurance_data_analyst_agent.infrastructure.persistence.models import Base

MIGRATIONS_DIRECTORY = Path(__file__).resolve().parent / "migrations"


def normalize_database_url(url: str) -> str:
    """Point plain PostgreSQL URLs at the installed psycopg 3 driver."""
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url


def create_database_engine(database_url: str, *, echo: bool = False) -> Engine:
    normalized_url = normalize_database_url(database_url)

    if normalized_url.startswith("sqlite"):
        return create_engine(
            normalized_url,
            echo=echo,
            connect_args={"check_same_thread": False},
        )

    return create_engine(normalized_url, echo=echo, pool_pre_ping=True)


def create_session_factory(engine: Engine) -> Callable[[], Session]:
    return sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )


def run_migrations(database_url: str) -> None:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIRECTORY))
    # configparser treats '%' as interpolation syntax; escape percent-encoded
    # credentials (for example '%40' for '@') so Alembic reads them back intact.
    config.set_main_option(
        "sqlalchemy.url",
        normalize_database_url(database_url).replace("%", "%%"),
    )
    command.upgrade(config, "head")


def initialize_database(database_url: str) -> None:
    """SQLite: create tables directly. PostgreSQL: apply Alembic migrations."""
    normalized_url = normalize_database_url(database_url)

    if make_url(normalized_url).get_backend_name() == "sqlite":
        engine = create_database_engine(normalized_url)
        Base.metadata.create_all(bind=engine)
        engine.dispose()
        return

    run_migrations(database_url)
