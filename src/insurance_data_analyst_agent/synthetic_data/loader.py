from __future__ import annotations

from sqlalchemy import Engine, delete, insert

from insurance_data_analyst_agent.infrastructure.persistence.models import (
    Claim,
    Exposure,
    Policy,
)
from insurance_data_analyst_agent.synthetic_data.generator import (
    SEED,
    generate_synthetic_rows,
)

POLICY_COLUMNS = (
    "policy_id",
    "province",
    "line_of_business",
    "underwriting_year",
    "written_premium",
)
EXPOSURE_COLUMNS = ("exposure_id", "policy_id", "exposure_year", "exposure_units")
CLAIM_COLUMNS = ("claim_id", "policy_id", "claim_year", "claim_type", "paid_amount")


def load_synthetic_data(
    engine: Engine,
    seed: int = SEED,
    policies_per_segment_year: int = 30,
) -> None:
    """Replace the content of the migrated tables with synthetic data."""
    policies, exposures, claims = generate_synthetic_rows(
        seed, policies_per_segment_year
    )

    with engine.begin() as connection:
        connection.execute(delete(Claim))
        connection.execute(delete(Exposure))
        connection.execute(delete(Policy))

        connection.execute(
            insert(Policy),
            [dict(zip(POLICY_COLUMNS, row, strict=True)) for row in policies],
        )
        connection.execute(
            insert(Exposure),
            [dict(zip(EXPOSURE_COLUMNS, row, strict=True)) for row in exposures],
        )
        if claims:
            connection.execute(
                insert(Claim),
                [dict(zip(CLAIM_COLUMNS, row, strict=True)) for row in claims],
            )
