from __future__ import annotations

from typing import Any

from insurance_data_analyst_agent.infrastructure.persistence.access import DataSource
from insurance_data_analyst_agent.models.analytics import SeverityRequest
from insurance_data_analyst_agent.tools.segment_query import (
    build_segment_query,
    execute_segment_statement,
)

CALCULATION_DEFINITION = (
    "average_severity = paid_claim_amount / claim_count, by underwriting year. "
    "All claims of the policies underwritten in the selected years are counted, "
    "whatever the claim year. Severity is null when a segment has no claim."
)


def get_claim_severity(
    database_path: DataSource,
    request: SeverityRequest,
) -> list[dict[str, Any]]:
    query = build_segment_query(request)

    sql = f"""
        WITH claims_by_policy AS (
            SELECT
                policy_id,
                COUNT(*) AS claim_count,
                SUM(paid_amount) AS paid_claim_amount
            FROM claims
            GROUP BY policy_id
        )
        SELECT
            {query.select_clause},
            CAST(COALESCE(SUM(cbp.claim_count), 0) AS INTEGER) AS claim_count,
            ROUND(COALESCE(SUM(cbp.paid_claim_amount), 0), 2) AS paid_claim_amount,
            ROUND(
                1.0 * COALESCE(SUM(cbp.paid_claim_amount), 0)
                / NULLIF(SUM(cbp.claim_count), 0),
                2
            ) AS average_severity
        FROM policies AS p
        LEFT JOIN claims_by_policy AS cbp
            ON p.policy_id = cbp.policy_id
        WHERE {query.where_clause}
        GROUP BY {query.group_by_clause}
        ORDER BY {query.group_by_clause}
    """

    return execute_segment_statement(database_path, sql, query.parameters)
