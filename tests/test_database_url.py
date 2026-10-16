from __future__ import annotations

from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.engine import make_url

from insurance_data_analyst_agent.infrastructure.persistence import database

PERCENT_ENCODED_URL = (
    "postgresql+psycopg://analyst_app:pa%25ss%40word@localhost:5432/analyst"
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("postgresql://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
        ("postgres://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
        ("sqlite:///x.db", "sqlite:///x.db"),
    ],
)
def test_normalize_database_url(raw: str, expected: str) -> None:
    assert database.normalize_database_url(raw) == expected


def test_normalize_keeps_percent_encoded_password() -> None:
    normalized = database.normalize_database_url(PERCENT_ENCODED_URL)

    assert normalized == PERCENT_ENCODED_URL
    assert make_url(normalized).password == "pa%ss@word"


def test_run_migrations_keeps_percent_encoded_credentials(monkeypatch) -> None:
    captured: list[Config] = []
    monkeypatch.setattr(
        database.command, "upgrade", lambda config, rev: captured.append(config)
    )

    database.run_migrations(PERCENT_ENCODED_URL)

    configured = captured[0].get_main_option("sqlalchemy.url")
    assert configured == database.normalize_database_url(PERCENT_ENCODED_URL)


def test_migrations_create_tables_and_are_idempotent(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'migrated.db'}"

    database.run_migrations(url)
    database.run_migrations(url)

    engine = database.create_database_engine(url)
    tables = set(inspect(engine).get_table_names())
    engine.dispose()

    assert {"policies", "exposure", "claims", "alembic_version"} <= tables


def test_initialize_database_creates_tables_for_sqlite(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'direct.db'}"

    database.initialize_database(url)

    engine = database.create_database_engine(url)
    tables = set(inspect(engine).get_table_names())
    engine.dispose()

    assert {"policies", "exposure", "claims"} <= tables
