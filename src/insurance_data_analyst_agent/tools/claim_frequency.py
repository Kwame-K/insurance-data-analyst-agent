from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import bindparam, text

from insurance_data_analyst_agent.infrastructure.persistence.access import (
    DataSource,
    connect,
)
from insurance_data_analyst_agent.models.analytics import ClaimFrequencyRequest

ALLOWED_SEGMENT_DIMENSIONS = {
    "province": "p.province",
    "line_of_business": "p.line_of_business",
}

CALCULATION_DEFINITION = (
    "Claim frequency = number of claims / exposure units, by calendar year. "
    "Claims are counted by claim_year only on policies with exposure in the "
    "same year; year_over_year_change compares with the previous requested "
    "year of the same segment."
)


def get_claim_frequency_trend(
    database_path: DataSource,
    request: ClaimFrequencyRequest,
) -> list[dict[str, Any]]:
    segments = [dimension.value for dimension in request.dimensions]

    segment_columns = [ALLOWED_SEGMENT_DIMENSIONS[name] for name in segments]
    select_segments = [
        f"{column} AS {name}"
        for name, column in zip(segments, segment_columns, strict=True)
    ]

    where_clauses: list[str] = []
    parameters: dict[str, Any] = {"years": list(request.years)}

    if request.provinces:
        where_clauses.append("p.province IN :provinces")
        parameters["provinces"] = list(request.provinces)

    if request.lines_of_business:
        where_clauses.append("p.line_of_business IN :lines_of_business")
        parameters["lines_of_business"] = list(request.lines_of_business)

    select_clause = ", ".join(["e.exposure_year AS year", *select_segments])
    group_clause = ", ".join([*segment_columns, "e.exposure_year"])
    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    statement = text(
        f"""
        WITH exposure_by_policy_year AS (
            SELECT
                policy_id,
                exposure_year,
                SUM(exposure_units) AS exposure_units
            FROM exposure
            WHERE exposure_year IN :years
            GROUP BY policy_id, exposure_year
        ),
        claims_by_policy_year AS (
            SELECT
                policy_id,
                claim_year,
                COUNT(*) AS claim_count
            FROM claims
            WHERE claim_year IN :years
            GROUP BY policy_id, claim_year
        )
        SELECT
            {select_clause},
            COALESCE(SUM(c.claim_count), 0) AS claim_count,
            ROUND(SUM(e.exposure_units), 4) AS exposure_units,
            ROUND(
                1.0 * COALESCE(SUM(c.claim_count), 0)
                / NULLIF(SUM(e.exposure_units), 0),
                6
            ) AS claim_frequency
        FROM exposure_by_policy_year AS e
        JOIN policies AS p
            ON p.policy_id = e.policy_id
        LEFT JOIN claims_by_policy_year AS c
            ON c.policy_id = e.policy_id
            AND c.claim_year = e.exposure_year
        {where_sql}
        GROUP BY {group_clause}
        ORDER BY {group_clause}
        """
    ).bindparams(*(bindparam(name, expanding=True) for name in parameters))

    with connect(database_path) as connection:
        rows = connection.execute(statement, parameters).mappings().all()

    results = [
        {
            key: float(value) if isinstance(value, Decimal) else value
            for key, value in row.items()
        }
        for row in rows
    ]

    return _add_year_over_year_change(results, segments)


def _add_year_over_year_change(
    rows: list[dict[str, Any]],
    segments: list[str],
) -> list[dict[str, Any]]:
    """Add the relative change versus the previous year of the same segment."""
    previous_frequency: dict[tuple[Any, ...], float | None] = {}
    enriched: list[dict[str, Any]] = []

    for row in rows:
        key = tuple(row[name] for name in segments)
        previous = previous_frequency.get(key)
        current = row["claim_frequency"]

        change: float | None = None
        if previous is not None and current is not None and previous != 0:
            change = round((current - previous) / previous, 6)

        enriched.append({**row, "year_over_year_change": change})
        previous_frequency[key] = current

    return enriched
