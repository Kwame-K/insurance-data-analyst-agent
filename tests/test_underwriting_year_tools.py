from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
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
    Dimension,
    ExposureSummaryRequest,
    LossRatioRequest,
    PortfolioQualityRequest,
    SeverityRequest,
)
from insurance_data_analyst_agent.synthetic_data.generator import (
    create_synthetic_database,
)
from insurance_data_analyst_agent.tools.exposure_summary import get_exposure_summary
from insurance_data_analyst_agent.tools.loss_ratio import get_loss_ratio_by_segment
from insurance_data_analyst_agent.tools.portfolio_quality import (
    get_portfolio_quality_metrics,
)
from insurance_data_analyst_agent.tools.severity import get_claim_severity

PROPERTY = "commercial_property"
AUTO = "commercial_auto"
LIABILITY = "general_liability"

SEGMENTS = [Dimension.PROVINCE, Dimension.UNDERWRITING_YEAR]
YEARS = [2024, 2025]


@pytest.fixture
def tiny_database(tmp_path: Path) -> Path:
    path = tmp_path / "tiny.db"
    engine = create_database_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)

    policies = [
        ("P1", "QC", PROPERTY, 2025, 3000.0),
        ("P2", "QC", PROPERTY, 2025, 1000.0),
        ("P6", "QC", PROPERTY, 2025, 1000.0),
        ("P3", "ON", AUTO, 2025, 2000.0),
        ("P4", "QC", PROPERTY, 2024, 1000.0),
        ("P5", "BC", LIABILITY, 2025, 1000.0),
    ]
    exposures = [
        ("E1", "P1", 2025, 1.0),
        ("E2", "P1", 2025, 0.5),
        ("E3", "P2", 2025, 1.0),
        ("E6", "P6", 2025, 1.0),
        ("E4", "P3", 2025, 1.0),
        ("E5", "P4", 2024, 1.0),
        ("E7", "P5", 2025, 1.0),
    ]
    claims = [
        ("C1", "P1", 2025, 1000.0),
        ("C2", "P1", 2026, 500.0),
        ("C6", "P2", 2025, 250.0),
        ("C3", "P3", 2025, 600.0),
        ("C4", "P4", 2024, 400.0),
    ]

    with engine.begin() as connection:
        connection.execute(
            insert(Policy),
            [
                {
                    "policy_id": policy_id,
                    "province": province,
                    "line_of_business": line,
                    "underwriting_year": year,
                    "written_premium": premium,
                }
                for policy_id, province, line, year, premium in policies
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
                    "paid_amount": paid,
                }
                for claim_id, policy_id, year, paid in claims
            ],
        )
    engine.dispose()
    return path


def by_segment(rows: list[dict[str, Any]]) -> dict[tuple[str, int], dict[str, Any]]:
    return {(row["province"], row["underwriting_year"]): row for row in rows}


def test_severity_matches_hand_calculation(tiny_database: Path) -> None:
    rows = get_claim_severity(
        tiny_database,
        SeverityRequest(underwriting_years=YEARS, dimensions=SEGMENTS),
    )
    segments = by_segment(rows)

    assert [(r["province"], r["underwriting_year"]) for r in rows] == [
        ("BC", 2025),
        ("ON", 2025),
        ("QC", 2024),
        ("QC", 2025),
    ]
    assert segments[("QC", 2025)]["claim_count"] == 3
    assert segments[("QC", 2025)]["paid_claim_amount"] == pytest.approx(1750.0)
    assert segments[("QC", 2025)]["average_severity"] == pytest.approx(583.33)
    assert segments[("ON", 2025)]["average_severity"] == pytest.approx(600.0)
    assert segments[("QC", 2024)]["average_severity"] == pytest.approx(400.0)
    assert segments[("BC", 2025)]["claim_count"] == 0
    assert segments[("BC", 2025)]["average_severity"] is None


def test_severity_counts_claims_whatever_the_claim_year(
    tiny_database: Path,
) -> None:
    rows = get_claim_severity(
        tiny_database,
        SeverityRequest(underwriting_years=[2025], provinces=["QC"]),
    )

    assert len(rows) == 1
    assert rows[0]["claim_count"] == 3
    assert isinstance(rows[0]["claim_count"], int)


def test_exposure_summary_matches_hand_calculation(tiny_database: Path) -> None:
    rows = get_exposure_summary(
        tiny_database,
        ExposureSummaryRequest(underwriting_years=YEARS, dimensions=SEGMENTS),
    )
    segments = by_segment(rows)

    qc_2025 = segments[("QC", 2025)]
    assert qc_2025["policy_count"] == 3
    assert qc_2025["exposure_units"] == pytest.approx(3.5)
    assert qc_2025["written_premium"] == pytest.approx(5000.0)
    assert qc_2025["average_exposure_per_policy"] == pytest.approx(1.1667, abs=1e-4)
    assert segments[("QC", 2024)]["policy_count"] == 1
    assert segments[("BC", 2025)]["exposure_units"] == pytest.approx(1.0)


def test_portfolio_quality_matches_hand_calculation(tiny_database: Path) -> None:
    rows = get_portfolio_quality_metrics(
        tiny_database,
        PortfolioQualityRequest(underwriting_years=YEARS, dimensions=SEGMENTS),
    )
    segments = by_segment(rows)

    qc_2025 = segments[("QC", 2025)]
    assert qc_2025["policy_count"] == 3
    assert qc_2025["policies_with_claims"] == 2
    assert qc_2025["claim_count"] == 3
    assert qc_2025["written_premium"] == pytest.approx(5000.0)
    assert qc_2025["paid_claim_amount"] == pytest.approx(1750.0)
    assert qc_2025["exposure_units"] == pytest.approx(3.5)
    assert qc_2025["loss_ratio"] == pytest.approx(0.35)
    assert qc_2025["claim_frequency"] == pytest.approx(0.857143, abs=1e-6)
    assert qc_2025["average_severity"] == pytest.approx(583.33)
    assert qc_2025["premium_per_exposure_unit"] == pytest.approx(1428.57)
    assert qc_2025["share_of_policies_with_claims"] == pytest.approx(0.666667, abs=1e-6)

    bc_2025 = segments[("BC", 2025)]
    assert bc_2025["loss_ratio"] == pytest.approx(0.0)
    assert bc_2025["claim_frequency"] == pytest.approx(0.0)
    assert bc_2025["average_severity"] is None
    assert bc_2025["share_of_policies_with_claims"] == pytest.approx(0.0)


def test_portfolio_wide_quality_for_one_year(tiny_database: Path) -> None:
    rows = get_portfolio_quality_metrics(
        tiny_database, PortfolioQualityRequest(underwriting_years=[2025])
    )

    assert len(rows) == 1
    assert rows[0]["policy_count"] == 5
    assert rows[0]["written_premium"] == pytest.approx(8000.0)
    assert rows[0]["loss_ratio"] == pytest.approx(0.29375)
    assert rows[0]["average_severity"] == pytest.approx(587.5)
    assert rows[0]["share_of_policies_with_claims"] == pytest.approx(0.6)


def test_filters_restrict_segments(tiny_database: Path) -> None:
    rows = get_exposure_summary(
        tiny_database,
        ExposureSummaryRequest(
            underwriting_years=YEARS,
            lines_of_business=[AUTO],
        ),
    )

    assert len(rows) == 1
    assert rows[0]["policy_count"] == 1
    assert rows[0]["written_premium"] == pytest.approx(2000.0)


def test_unknown_year_returns_no_rows(tiny_database: Path) -> None:
    request = PortfolioQualityRequest(underwriting_years=[2099])

    assert get_portfolio_quality_metrics(tiny_database, request) == []


@pytest.fixture
def synthetic_database(tmp_path: Path) -> Path:
    path = tmp_path / "synthetic.db"
    create_synthetic_database(path, seed=42, policies_per_segment_year=10)
    return path


def test_quality_loss_ratio_matches_loss_ratio_tool(synthetic_database: Path) -> None:
    all_dimensions = [
        Dimension.PROVINCE,
        Dimension.LINE_OF_BUSINESS,
        Dimension.UNDERWRITING_YEAR,
    ]
    years = [2023, 2024, 2025]

    quality = get_portfolio_quality_metrics(
        synthetic_database,
        PortfolioQualityRequest(underwriting_years=years, dimensions=all_dimensions),
    )
    loss_ratio = get_loss_ratio_by_segment(
        synthetic_database,
        LossRatioRequest(underwriting_years=years, dimensions=all_dimensions),
    )

    assert len(quality) == len(loss_ratio)
    for q_row, l_row in zip(quality, loss_ratio, strict=True):
        assert q_row["loss_ratio"] == pytest.approx(l_row["loss_ratio"])
        assert q_row["written_premium"] == pytest.approx(l_row["written_premium"])
        assert q_row["paid_claim_amount"] == pytest.approx(l_row["paid_claim_amount"])


def test_claim_and_exposure_totals_match_the_tables(synthetic_database: Path) -> None:
    years = [2023, 2024, 2025]
    rows = get_portfolio_quality_metrics(
        synthetic_database,
        PortfolioQualityRequest(underwriting_years=years),
    )

    with sqlite3.connect(synthetic_database) as connection:
        claims, paid = connection.execute(
            "SELECT COUNT(*), SUM(paid_amount) FROM claims"
        ).fetchone()
        (exposure,) = connection.execute(
            "SELECT SUM(exposure_units) FROM exposure"
        ).fetchone()
        (policies,) = connection.execute("SELECT COUNT(*) FROM policies").fetchone()

    assert sum(row["claim_count"] for row in rows) == claims
    assert sum(row["paid_claim_amount"] for row in rows) == pytest.approx(paid, abs=0.1)
    assert sum(row["exposure_units"] for row in rows) == pytest.approx(
        exposure, abs=0.01
    )
    assert sum(row["policy_count"] for row in rows) == policies

    for row in rows:
        if row["claim_count"]:
            assert row["average_severity"] * row["claim_count"] == pytest.approx(
                row["paid_claim_amount"], rel=1e-3
            )


@pytest.mark.parametrize(
    "model", [SeverityRequest, ExposureSummaryRequest, PortfolioQualityRequest]
)
@pytest.mark.parametrize(
    "arguments",
    [
        {"underwriting_years": []},
        {"underwriting_years": [1999]},
        {"underwriting_years": [2025, 2025]},
        {"underwriting_years": [2025], "dimensions": []},
        {"underwriting_years": [2025], "dimensions": ["province", "province"]},
        {"underwriting_years": [2025], "dimensions": ["postal_code"]},
        {"underwriting_years": [2025], "provinces": ["XX"]},
        {"underwriting_years": [2025], "lines_of_business": ["marine"]},
        {"underwriting_years": [2025], "sql": "DROP TABLE policies"},
    ],
)
def test_requests_reject_invalid_arguments(
    model: type[SeverityRequest], arguments: dict[str, Any]
) -> None:
    with pytest.raises(ValidationError):
        model.model_validate(arguments)


def test_requests_default_to_underwriting_year_dimension() -> None:
    request = SeverityRequest(underwriting_years=[2025])

    assert request.dimensions == [Dimension.UNDERWRITING_YEAR]
