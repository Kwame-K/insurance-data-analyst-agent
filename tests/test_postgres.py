from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy import text

from insurance_data_analyst_agent.infrastructure.persistence.database import (
    create_database_engine,
    run_migrations,
)
from insurance_data_analyst_agent.infrastructure.persistence.models import Base
from insurance_data_analyst_agent.models.analytics import Dimension, LossRatioRequest
from insurance_data_analyst_agent.synthetic_data.generator import (
    create_synthetic_database,
)
from insurance_data_analyst_agent.synthetic_data.loader import load_synthetic_data
from insurance_data_analyst_agent.tools.loss_ratio import get_loss_ratio_by_segment

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL is not set",
)

REQUEST = LossRatioRequest(
    underwriting_years=[2023, 2024, 2025],
    dimensions=[
        Dimension.PROVINCE,
        Dimension.LINE_OF_BUSINESS,
        Dimension.UNDERWRITING_YEAR,
    ],
)


def test_postgres_results_match_sqlite(tmp_path: Path) -> None:
    url = os.environ["TEST_DATABASE_URL"]
    engine = create_database_engine(url)

    with engine.begin() as connection:
        Base.metadata.drop_all(connection)
        connection.execute(text("DROP TABLE IF EXISTS alembic_version"))

    run_migrations(url)
    load_synthetic_data(engine, seed=42, policies_per_segment_year=10)

    legacy_path = tmp_path / "legacy.db"
    create_synthetic_database(legacy_path, seed=42, policies_per_segment_year=10)

    postgres_rows = get_loss_ratio_by_segment(engine, REQUEST)
    sqlite_rows = get_loss_ratio_by_segment(legacy_path, REQUEST)
    engine.dispose()

    assert len(postgres_rows) == len(sqlite_rows)
    for pg, lite in zip(postgres_rows, sqlite_rows, strict=True):
        assert pg["loss_ratio"] == pytest.approx(lite["loss_ratio"], abs=1e-5)
        assert pg["written_premium"] == pytest.approx(lite["written_premium"])
