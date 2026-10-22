from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import bindparam, text

from insurance_data_analyst_agent.infrastructure.persistence.access import (
    DataSource,
    connect,
)
from insurance_data_analyst_agent.models.analytics import UnderwritingYearRequest

ALLOWED_DIMENSIONS = {
    "province": "p.province",
    "line_of_business": "p.line_of_business",
    "underwriting_year": "p.underwriting_year",
}


@dataclass(frozen=True)
class SegmentQuery:
    """Fixed SQL fragments and bound parameters shared by cohort tools."""

    select_clause: str
    group_by_clause: str
    where_clause: str
    parameters: dict[str, Any]


def build_segment_query(request: UnderwritingYearRequest) -> SegmentQuery:
    """Map validated dimensions and filters to allow-listed SQL fragments."""
    names = [dimension.value for dimension in request.dimensions]
    columns = [ALLOWED_DIMENSIONS[name] for name in names]

    where_clauses = ["p.underwriting_year IN :years"]
    parameters: dict[str, Any] = {"years": list(request.underwriting_years)}

    if request.provinces:
        where_clauses.append("p.province IN :provinces")
        parameters["provinces"] = list(request.provinces)

    if request.lines_of_business:
        where_clauses.append("p.line_of_business IN :lines_of_business")
        parameters["lines_of_business"] = list(request.lines_of_business)

    return SegmentQuery(
        select_clause=", ".join(
            f"{column} AS {name}" for name, column in zip(names, columns, strict=True)
        ),
        group_by_clause=", ".join(columns),
        where_clause=" AND ".join(where_clauses),
        parameters=parameters,
    )


def execute_segment_statement(
    database_path: DataSource,
    sql: str,
    parameters: dict[str, Any],
) -> list[dict[str, Any]]:
    """Run one fixed statement with bound parameters and normalize decimals."""
    statement = text(sql).bindparams(
        *(bindparam(name, expanding=True) for name in parameters)
    )

    with connect(database_path) as connection:
        rows = connection.execute(statement, parameters).mappings().all()

    return [
        {
            key: float(value) if isinstance(value, Decimal) else value
            for key, value in row.items()
        }
        for row in rows
    ]
