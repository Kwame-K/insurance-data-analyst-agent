from __future__ import annotations

from pathlib import Path

import pytest

from insurance_data_analyst_agent.database import get_available_underwriting_years
from insurance_data_analyst_agent.infrastructure.persistence.access import (
    describe_data_source,
)
from insurance_data_analyst_agent.infrastructure.persistence.database import (
    create_database_engine,
    run_migrations,
)
from insurance_data_analyst_agent.models.analytics import Dimension, LossRatioRequest
from insurance_data_analyst_agent.synthetic_data.generator import (
    create_synthetic_database,
)
from insurance_data_analyst_agent.synthetic_data.loader import load_synthetic_data
from insurance_data_analyst_agent.tools.loss_ratio import get_loss_ratio_by_segment

REQUEST = LossRatioRequest(
    underwriting_years=[2023, 2024, 2025],
    dimensions=[
        Dimension.PROVINCE,
        Dimension.LINE_OF_BUSINESS,
        Dimension.UNDERWRITING_YEAR,
    ],
)


def test_migrated_orm_database_matches_legacy_sqlite(tmp_path: Path) -> None:
    legacy_path = tmp_path / "legacy.db"
    create_synthetic_database(legacy_path, seed=42, policies_per_segment_year=10)

    url = f"sqlite:///{tmp_path / 'migrated.db'}"
    run_migrations(url)
    engine = create_database_engine(url)
    load_synthetic_data(engine, seed=42, policies_per_segment_year=10)

    try:
        assert get_available_underwriting_years(engine) == [2023, 2024, 2025]
        assert get_loss_ratio_by_segment(engine, REQUEST) == (
            get_loss_ratio_by_segment(legacy_path, REQUEST)
        )
    finally:
        engine.dispose()


def test_load_synthetic_data_is_repeatable(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'repeat.db'}"
    run_migrations(url)
    engine = create_database_engine(url)

    try:
        load_synthetic_data(engine, seed=1, policies_per_segment_year=2)
        first = get_loss_ratio_by_segment(engine, REQUEST)
        load_synthetic_data(engine, seed=1, policies_per_segment_year=2)

        assert get_loss_ratio_by_segment(engine, REQUEST) == first
    finally:
        engine.dispose()


def test_describe_data_source_never_exposes_credentials() -> None:
    engine = create_database_engine(
        "postgresql+psycopg://analyst_app:s3cret%25@db.internal:5432/analyst"
    )

    description = describe_data_source(engine)

    assert description == "postgresql:analyst"
    assert "s3cret" not in description
    assert "db.internal" not in description


def test_describe_data_source_keeps_sqlite_path(tmp_path: Path) -> None:
    assert describe_data_source(tmp_path / "x.db") == str(tmp_path / "x.db")


def test_missing_sqlite_path_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Database does not exist"):
        get_available_underwriting_years(tmp_path / "missing.db")
