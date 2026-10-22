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
    Policy,
)
from insurance_data_analyst_agent.models.analytics import (
    Dimension,
    LossRatioRequest,
)
from insurance_data_analyst_agent.tools.loss_ratio import (
    get_loss_ratio_by_segment,
)


@pytest.fixture
def whole_number_database(tmp_path: Path) -> Path:
    path = tmp_path / "whole_numbers.db"
    engine = create_database_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)

    with engine.begin() as connection:
        connection.execute(
            insert(Policy),
            [
                {
                    "policy_id": "P1",
                    "province": "QC",
                    "line_of_business": "commercial_property",
                    "underwriting_year": 2025,
                    "written_premium": 3000.0,
                }
            ],
        )
        connection.execute(
            insert(Claim),
            [
                {
                    "claim_id": "C1",
                    "policy_id": "P1",
                    "claim_year": 2025,
                    "claim_type": "fire",
                    "paid_amount": 1000.0,
                }
            ],
        )
    engine.dispose()
    return path


def test_loss_ratio_is_not_truncated_for_whole_number_amounts(
    whole_number_database: Path,
) -> None:
    request = LossRatioRequest(
        underwriting_years=[2025],
        dimensions=[Dimension.PROVINCE],
    )

    results = get_loss_ratio_by_segment(whole_number_database, request)

    assert len(results) == 1
    assert results[0]["loss_ratio"] == pytest.approx(0.333333, abs=1e-6)
