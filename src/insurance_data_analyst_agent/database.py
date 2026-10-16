from __future__ import annotations

from sqlalchemy import text

from insurance_data_analyst_agent.infrastructure.persistence.access import (
    DataSource,
    connect,
)


def get_available_underwriting_years(database_path: DataSource) -> list[int]:
    """Return all available underwriting years in ascending order."""
    with connect(database_path) as connection:
        rows = connection.execute(
            text(
                "SELECT DISTINCT underwriting_year "
                "FROM policies ORDER BY underwriting_year"
            )
        ).all()

    return [row[0] for row in rows]
