from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import bindparam, text

from insurance_data_analyst_agent.infrastructure.persistence.access import (
    DataSource,
    connect,
)
from insurance_data_analyst_agent.models.analytics import LossRatioRequest

ALLOWED_DIMENSIONS = {
    "province": "p.province",
    "line_of_business": "p.line_of_business",
    "underwriting_year": "p.underwriting_year",
}


def get_loss_ratio_by_segment(
    database_path: DataSource,
    request: LossRatioRequest,
) -> list[dict[str, Any]]:
    selected_dimensions = [dimension.value for dimension in request.dimensions]

    group_columns = [ALLOWED_DIMENSIONS[dimension] for dimension in selected_dimensions]
    select_dimensions = [
        f"{column} AS {dimension}"
        for dimension, column in zip(selected_dimensions, group_columns, strict=True)
    ]

    where_clauses = ["p.underwriting_year IN :years"]
    parameters: dict[str, Any] = {"years": list(request.underwriting_years)}

    if request.provinces:
        where_clauses.append("p.province IN :provinces")
        parameters["provinces"] = list(request.provinces)

    if request.lines_of_business:
        where_clauses.append("p.line_of_business IN :lines_of_business")
        parameters["lines_of_business"] = list(request.lines_of_business)

    select_clause = ", ".join(select_dimensions)
    group_by_clause = ", ".join(group_columns)
    where_clause = " AND ".join(where_clauses)

    statement = text(
        f"""
        WITH claims_by_policy AS (
            SELECT
                policy_id,
                SUM(paid_amount) AS paid_claim_amount
            FROM claims
            GROUP BY policy_id
        )
        SELECT
            {select_clause},
            ROUND(SUM(p.written_premium), 2) AS written_premium,
            ROUND(COALESCE(SUM(cbp.paid_claim_amount), 0), 2) AS paid_claim_amount,
            ROUND(
                COALESCE(SUM(cbp.paid_claim_amount), 0)
                / NULLIF(SUM(p.written_premium), 0),
                6
            ) AS loss_ratio
        FROM policies AS p
        LEFT JOIN claims_by_policy AS cbp
            ON p.policy_id = cbp.policy_id
        WHERE {where_clause}
        GROUP BY {group_by_clause}
        ORDER BY {group_by_clause}
        """
    ).bindparams(*(bindparam(name, expanding=True) for name in parameters))

    with connect(database_path) as connection:
        rows = connection.execute(statement, parameters).mappings().all()

    return [
        {
            key: float(value) if isinstance(value, Decimal) else value
            for key, value in row.items()
        }
        for row in rows
    ]
