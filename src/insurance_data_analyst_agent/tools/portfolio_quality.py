from __future__ import annotations

from typing import Any

from insurance_data_analyst_agent.infrastructure.persistence.access import DataSource
from insurance_data_analyst_agent.models.analytics import PortfolioQualityRequest
from insurance_data_analyst_agent.tools.segment_query import (
    build_segment_query,
    execute_segment_statement,
)

CALCULATION_DEFINITION = (
    "Portfolio quality metrics on an underwriting-year (policy cohort) basis: "
    "loss_ratio = paid_claim_amount / written_premium; "
    "claim_frequency = claim_count / exposure_units; "
    "average_severity = paid_claim_amount / claim_count; "
    "premium_per_exposure_unit = written_premium / exposure_units; "
    "share_of_policies_with_claims = policies_with_claims / policy_count. "
    "Claims and exposure are those of the policies underwritten in the "
    "selected years, whatever the claim or exposure year."
)


def get_portfolio_quality_metrics(
    database_path: DataSource,
    request: PortfolioQualityRequest,
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
        ),
        exposure_by_policy AS (
            SELECT
                policy_id,
                SUM(exposure_units) AS exposure_units
            FROM exposure
            GROUP BY policy_id
        )
        SELECT
            {query.select_clause},
            COUNT(*) AS policy_count,
            COUNT(cbp.policy_id) AS policies_with_claims,
            CAST(COALESCE(SUM(cbp.claim_count), 0) AS INTEGER) AS claim_count,
            ROUND(SUM(p.written_premium), 2) AS written_premium,
            ROUND(COALESCE(SUM(cbp.paid_claim_amount), 0), 2) AS paid_claim_amount,
            ROUND(COALESCE(SUM(ebp.exposure_units), 0), 4) AS exposure_units,
            ROUND(
                1.0 * COALESCE(SUM(cbp.paid_claim_amount), 0)
                / NULLIF(SUM(p.written_premium), 0),
                6
            ) AS loss_ratio,
            ROUND(
                1.0 * COALESCE(SUM(cbp.claim_count), 0)
                / NULLIF(SUM(ebp.exposure_units), 0),
                6
            ) AS claim_frequency,
            ROUND(
                1.0 * COALESCE(SUM(cbp.paid_claim_amount), 0)
                / NULLIF(SUM(cbp.claim_count), 0),
                2
            ) AS average_severity,
            ROUND(
                1.0 * SUM(p.written_premium)
                / NULLIF(SUM(ebp.exposure_units), 0),
                2
            ) AS premium_per_exposure_unit,
            ROUND(
                1.0 * COUNT(cbp.policy_id)
                / NULLIF(COUNT(*), 0),
                6
            ) AS share_of_policies_with_claims
        FROM policies AS p
        LEFT JOIN claims_by_policy AS cbp
            ON p.policy_id = cbp.policy_id
        LEFT JOIN exposure_by_policy AS ebp
            ON p.policy_id = ebp.policy_id
        WHERE {query.where_clause}
        GROUP BY {query.group_by_clause}
        ORDER BY {query.group_by_clause}
    """

    return execute_segment_statement(database_path, sql, query.parameters)
