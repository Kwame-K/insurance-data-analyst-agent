from __future__ import annotations

from typing import Any

from insurance_data_analyst_agent.infrastructure.persistence.access import DataSource
from insurance_data_analyst_agent.models.analytics import ExposureSummaryRequest
from insurance_data_analyst_agent.tools.segment_query import (
    build_segment_query,
    execute_segment_statement,
)

CALCULATION_DEFINITION = (
    "Exposure summary by underwriting year: policy_count, exposure_units "
    "(all exposure rows of the policies underwritten in the selected years), "
    "written_premium, and average_exposure_per_policy = exposure_units / "
    "policy_count."
)


def get_exposure_summary(
    database_path: DataSource,
    request: ExposureSummaryRequest,
) -> list[dict[str, Any]]:
    query = build_segment_query(request)

    sql = f"""
        WITH exposure_by_policy AS (
            SELECT
                policy_id,
                SUM(exposure_units) AS exposure_units
            FROM exposure
            GROUP BY policy_id
        )
        SELECT
            {query.select_clause},
            COUNT(*) AS policy_count,
            ROUND(COALESCE(SUM(ebp.exposure_units), 0), 4) AS exposure_units,
            ROUND(SUM(p.written_premium), 2) AS written_premium,
            ROUND(
                1.0 * COALESCE(SUM(ebp.exposure_units), 0)
                / NULLIF(COUNT(*), 0),
                4
            ) AS average_exposure_per_policy
        FROM policies AS p
        LEFT JOIN exposure_by_policy AS ebp
            ON p.policy_id = ebp.policy_id
        WHERE {query.where_clause}
        GROUP BY {query.group_by_clause}
        ORDER BY {query.group_by_clause}
    """

    return execute_segment_statement(database_path, sql, query.parameters)
