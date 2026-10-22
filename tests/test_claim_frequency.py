from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import insert

from insurance_data_analyst_agent.infrastructure.persistence.database import (
    create_database_engine,
)
from insurance_data_analyst_agent.infrastructure.persistence.models import (
    Base,
    Claim,
    Exposure,
    Policy,
)
from insurance_data_analyst_agent.models.analytics import (
    ClaimFrequencyRequest,
    Dimension,
)
from insurance_data_analyst_agent.synthetic_data.generator import (
    create_synthetic_database,
)
from insurance_data_analyst_agent.tools.claim_frequency import (
    get_claim_frequency_trend,
)

PROPERTY = "commercial_property"
AUTO = "commercial_auto"


@pytest.fixture
def tiny_database(tmp_path: Path) -> Path:
    path = tmp_path / "tiny.db"
    engine = create_database_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)

    policies = [
        ("P1", "QC", PROPERTY),
        ("P2", "QC", PROPERTY),
        ("P3", "ON", AUTO),
        ("P4", "BC", AUTO),
    ]
    exposures = [
        ("E1", "P1", 2024, 1.0),
        ("E2", "P1", 2025, 1.0),
        ("E3", "P2", 2024, 0.25),
        ("E4", "P2", 2024, 0.25),
        ("E5", "P2", 2025, 1.0),
        ("E6", "P3", 2024, 1.0),
        ("E7", "P3", 2025, 1.0),
    ]
    claims = [
        ("C1", "P1", 2024),
        ("C2", "P1", 2024),
        ("C3", "P1", 2025),
        ("C4", "P2", 2024),
        ("C5", "P2", 2025),
        ("C6", "P2", 2025),
        ("C7", "P2", 2025),
        ("C8", "P3", 2025),
        ("C9", "P4", 2025),
        ("C10", "P1", 2026),
    ]

    with engine.begin() as connection:
        connection.execute(
            insert(Policy),
            [
                {
                    "policy_id": policy_id,
                    "province": province,
                    "line_of_business": line,
                    "underwriting_year": 2024,
                    "written_premium": 1000.0,
                }
                for policy_id, province, line in policies
            ],
        )
        connection.execute(
            insert(Exposure),
            [
                {
                    "exposure_id": exposure_id,
                    "policy_id": policy_id,
                    "exposure_year": year,
                    "exposure_units": units,
                }
                for exposure_id, policy_id, year, units in exposures
            ],
        )
        connection.execute(
            insert(Claim),
            [
                {
                    "claim_id": claim_id,
                    "policy_id": policy_id,
                    "claim_year": year,
                    "claim_type": "fire",
                    "paid_amount": 100.0,
                }
                for claim_id, policy_id, year in claims
            ],
        )
    engine.dispose()
    return path


def test_portfolio_trend_matches_hand_calculation(tiny_database: Path) -> None:
    request = ClaimFrequencyRequest(years=[2024, 2025])

    results = get_claim_frequency_trend(tiny_database, request)

    assert [row["year"] for row in results] == [2024, 2025]
    assert results[0]["claim_count"] == 3
    assert results[0]["exposure_units"] == pytest.approx(2.5)
    assert results[0]["claim_frequency"] == pytest.approx(1.2)
    assert results[0]["year_over_year_change"] is None
    assert results[1]["claim_count"] == 5
    assert results[1]["exposure_units"] == pytest.approx(3.0)
    assert results[1]["claim_frequency"] == pytest.approx(1.666667, abs=1e-6)
    assert results[1]["year_over_year_change"] == pytest.approx(0.388889, abs=1e-6)


def test_claims_without_exposure_are_not_counted(tiny_database: Path) -> None:
    request = ClaimFrequencyRequest(
        years=[2024, 2025],
        dimensions=[Dimension.PROVINCE],
    )

    results = get_claim_frequency_trend(tiny_database, request)

    assert {row["province"] for row in results} == {"QC", "ON"}


def test_trend_by_province_orders_by_segment_then_year(tiny_database: Path) -> None:
    request = ClaimFrequencyRequest(
        years=[2024, 2025],
        dimensions=[Dimension.PROVINCE],
    )

    results = get_claim_frequency_trend(tiny_database, request)

    assert [(row["province"], row["year"]) for row in results] == [
        ("ON", 2024),
        ("ON", 2025),
        ("QC", 2024),
        ("QC", 2025),
    ]
    on_2024, on_2025, qc_2024, qc_2025 = results
    assert on_2024["claim_frequency"] == 0
    assert on_2025["claim_frequency"] == pytest.approx(1.0)
    assert on_2025["year_over_year_change"] is None
    assert qc_2024["claim_frequency"] == pytest.approx(2.0)
    assert qc_2025["claim_frequency"] == pytest.approx(2.0)
    assert qc_2025["year_over_year_change"] == pytest.approx(0.0)


def test_filters_restrict_the_segment(tiny_database: Path) -> None:
    request = ClaimFrequencyRequest(
        years=[2024, 2025],
        provinces=["ON"],
        lines_of_business=[AUTO],
    )

    results = get_claim_frequency_trend(tiny_database, request)

    assert [row["claim_count"] for row in results] == [0, 1]


def test_years_without_data_return_no_rows(tiny_database: Path) -> None:
    request = ClaimFrequencyRequest(years=[2010, 2011])

    assert get_claim_frequency_trend(tiny_database, request) == []


def test_missing_database_raises(tmp_path: Path) -> None:
    request = ClaimFrequencyRequest(years=[2024, 2025])

    with pytest.raises(FileNotFoundError):
        get_claim_frequency_trend(tmp_path / "missing.db", request)


def test_synthetic_database_returns_valid_rows(tmp_path: Path) -> None:
    path = tmp_path / "synthetic.db"
    create_synthetic_database(path, seed=42, policies_per_segment_year=10)
    request = ClaimFrequencyRequest(
        years=[2023, 2024, 2025],
        dimensions=[Dimension.PROVINCE, Dimension.LINE_OF_BUSINESS],
    )

    results = get_claim_frequency_trend(path, request)

    assert results
    assert {
        "year",
        "province",
        "line_of_business",
        "claim_count",
        "exposure_units",
        "claim_frequency",
        "year_over_year_change",
    } == set(results[0])
    assert all(row["claim_frequency"] >= 0 for row in results)
