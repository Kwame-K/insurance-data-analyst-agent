from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine

from insurance_data_analyst_agent.infrastructure.persistence.database import (
    create_database_engine,
    run_migrations,
)
from insurance_data_analyst_agent.infrastructure.persistence.models import Base
from insurance_data_analyst_agent.models.analytics import (
    ClaimFrequencyRequest,
    Dimension,
    ExposureSummaryRequest,
    LossRatioRequest,
    PortfolioQualityRequest,
    SeverityRequest,
)
from insurance_data_analyst_agent.synthetic_data.generator import (
    create_synthetic_database,
)
from insurance_data_analyst_agent.synthetic_data.loader import load_synthetic_data
from insurance_data_analyst_agent.tools.claim_frequency import get_claim_frequency_trend
from insurance_data_analyst_agent.tools.exposure_summary import get_exposure_summary
from insurance_data_analyst_agent.tools.loss_ratio import get_loss_ratio_by_segment
from insurance_data_analyst_agent.tools.portfolio_quality import (
    get_portfolio_quality_metrics,
)
from insurance_data_analyst_agent.tools.severity import get_claim_severity

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


@pytest.fixture(scope="module")
def databases(
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[tuple[Engine, Path]]:
    """Same seeded data in PostgreSQL (migrated) and in a SQLite file."""
    url = os.environ["TEST_DATABASE_URL"]
    engine = create_database_engine(url)

    with engine.begin() as connection:
        Base.metadata.drop_all(connection)
        connection.execute(text("DROP TABLE IF EXISTS alembic_version"))

    run_migrations(url)
    load_synthetic_data(engine, seed=42, policies_per_segment_year=10)

    legacy_path = tmp_path_factory.mktemp("postgres_parity") / "legacy.db"
    create_synthetic_database(legacy_path, seed=42, policies_per_segment_year=10)

    yield engine, legacy_path

    engine.dispose()


# SQL ROUND digits per field. PostgreSQL rounds exact NUMERIC values, SQLite
# rounds binary floats, so a value sitting on a rounding tie can differ by one
# unit of the last digit between the two engines.
ROUNDING_STEP = {
    "average_severity": 0.01,
    "paid_claim_amount": 0.01,
    "written_premium": 0.01,
    "premium_per_exposure_unit": 0.01,
    "exposure_units": 0.0001,
    "average_exposure_per_policy": 0.0001,
}
DEFAULT_STEP = 1e-5


def assert_rows_match(
    postgres_rows: list[dict[str, Any]],
    sqlite_rows: list[dict[str, Any]],
) -> None:
    assert postgres_rows
    assert len(postgres_rows) == len(sqlite_rows)

    for pg, lite in zip(postgres_rows, sqlite_rows, strict=True):
        assert pg.keys() == lite.keys()
        for key, expected in lite.items():
            if isinstance(expected, float):
                step = ROUNDING_STEP.get(key, DEFAULT_STEP)
                assert pg[key] == pytest.approx(expected, abs=step * 1.01), key
            else:
                assert pg[key] == expected, key


def test_postgres_results_match_sqlite(databases: tuple[Engine, Path]) -> None:
    engine, legacy_path = databases

    postgres_rows = get_loss_ratio_by_segment(engine, REQUEST)
    sqlite_rows = get_loss_ratio_by_segment(legacy_path, REQUEST)

    assert len(postgres_rows) == len(sqlite_rows)
    for pg, lite in zip(postgres_rows, sqlite_rows, strict=True):
        assert pg["loss_ratio"] == pytest.approx(lite["loss_ratio"], abs=1e-5)
        assert pg["written_premium"] == pytest.approx(lite["written_premium"])


@pytest.mark.parametrize(
    "dimensions",
    [
        [],
        [Dimension.PROVINCE],
        [Dimension.PROVINCE, Dimension.LINE_OF_BUSINESS],
    ],
    ids=["portfolio", "province", "province-and-line"],
)
def test_postgres_claim_frequency_matches_sqlite(
    databases: tuple[Engine, Path],
    dimensions: list[Dimension],
) -> None:
    engine, legacy_path = databases
    request = ClaimFrequencyRequest(
        years=[2023, 2024, 2025],
        dimensions=dimensions,
    )

    postgres_rows = get_claim_frequency_trend(engine, request)
    sqlite_rows = get_claim_frequency_trend(legacy_path, request)

    assert_rows_match(postgres_rows, sqlite_rows)


def test_postgres_claim_frequency_filters_match_sqlite(
    databases: tuple[Engine, Path],
) -> None:
    engine, legacy_path = databases
    request = ClaimFrequencyRequest(
        years=[2024, 2025],
        dimensions=[Dimension.LINE_OF_BUSINESS],
        provinces=["QC", "ON"],
        lines_of_business=["commercial_property", "commercial_auto"],
    )

    postgres_rows = get_claim_frequency_trend(engine, request)
    sqlite_rows = get_claim_frequency_trend(legacy_path, request)

    assert_rows_match(postgres_rows, sqlite_rows)
    assert all(
        row["line_of_business"] in {"commercial_property", "commercial_auto"}
        for row in postgres_rows
    )


UNDERWRITING_YEAR_TOOLS = [
    (get_claim_severity, SeverityRequest),
    (get_exposure_summary, ExposureSummaryRequest),
    (get_portfolio_quality_metrics, PortfolioQualityRequest),
]


@pytest.mark.parametrize(
    ("tool", "request_model"),
    UNDERWRITING_YEAR_TOOLS,
    ids=["severity", "exposure-summary", "portfolio-quality"],
)
@pytest.mark.parametrize(
    "dimensions",
    [
        [Dimension.UNDERWRITING_YEAR],
        [Dimension.PROVINCE, Dimension.UNDERWRITING_YEAR],
        [
            Dimension.PROVINCE,
            Dimension.LINE_OF_BUSINESS,
            Dimension.UNDERWRITING_YEAR,
        ],
    ],
    ids=["year", "province-year", "all"],
)
def test_postgres_underwriting_year_tools_match_sqlite(
    databases: tuple[Engine, Path],
    tool: Any,
    request_model: Any,
    dimensions: list[Dimension],
) -> None:
    engine, legacy_path = databases
    request = request_model(
        underwriting_years=[2023, 2024, 2025],
        dimensions=dimensions,
    )

    assert_rows_match(tool(engine, request), tool(legacy_path, request))


@pytest.mark.parametrize(
    ("tool", "request_model"),
    UNDERWRITING_YEAR_TOOLS,
    ids=["severity", "exposure-summary", "portfolio-quality"],
)
def test_postgres_underwriting_year_filters_match_sqlite(
    databases: tuple[Engine, Path],
    tool: Any,
    request_model: Any,
) -> None:
    engine, legacy_path = databases
    request = request_model(
        underwriting_years=[2024, 2025],
        dimensions=[Dimension.LINE_OF_BUSINESS, Dimension.UNDERWRITING_YEAR],
        provinces=["QC", "ON"],
        lines_of_business=["commercial_property", "commercial_auto"],
    )

    postgres_rows = tool(engine, request)

    assert_rows_match(postgres_rows, tool(legacy_path, request))
    assert {row["line_of_business"] for row in postgres_rows} <= {
        "commercial_property",
        "commercial_auto",
    }
