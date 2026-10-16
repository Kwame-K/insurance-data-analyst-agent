"""Initial analytics schema.

Revision ID: 0001
Revises:
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "policies",
        sa.Column("policy_id", sa.String(32), primary_key=True),
        sa.Column("province", sa.String(2), nullable=False),
        sa.Column("line_of_business", sa.String(64), nullable=False),
        sa.Column("underwriting_year", sa.Integer(), nullable=False),
        sa.Column("written_premium", sa.Numeric(14, 2), nullable=False),
        sa.CheckConstraint("written_premium > 0", name="ck_policies_premium_positive"),
    )
    op.create_index(
        "ix_policies_segment",
        "policies",
        ["underwriting_year", "province", "line_of_business"],
    )

    op.create_table(
        "exposure",
        sa.Column("exposure_id", sa.String(32), primary_key=True),
        sa.Column(
            "policy_id",
            sa.String(32),
            sa.ForeignKey("policies.policy_id"),
            nullable=False,
        ),
        sa.Column("exposure_year", sa.Integer(), nullable=False),
        sa.Column("exposure_units", sa.Numeric(8, 4), nullable=False),
        sa.CheckConstraint("exposure_units > 0", name="ck_exposure_units_positive"),
    )
    op.create_index("ix_exposure_policy_id", "exposure", ["policy_id"])

    op.create_table(
        "claims",
        sa.Column("claim_id", sa.String(32), primary_key=True),
        sa.Column(
            "policy_id",
            sa.String(32),
            sa.ForeignKey("policies.policy_id"),
            nullable=False,
        ),
        sa.Column("claim_year", sa.Integer(), nullable=False),
        sa.Column("claim_type", sa.String(64), nullable=False),
        sa.Column("paid_amount", sa.Numeric(14, 2), nullable=False),
        sa.CheckConstraint("paid_amount >= 0", name="ck_claims_paid_non_negative"),
    )
    op.create_index("ix_claims_policy_id", "claims", ["policy_id"])


def downgrade() -> None:
    op.drop_table("claims")
    op.drop_table("exposure")
    op.drop_table("policies")
