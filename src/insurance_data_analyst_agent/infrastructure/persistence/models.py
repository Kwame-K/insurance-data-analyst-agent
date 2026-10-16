from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Policy(Base):
    __tablename__ = "policies"
    __table_args__ = (
        CheckConstraint("written_premium > 0", name="ck_policies_premium_positive"),
        Index(
            "ix_policies_segment",
            "underwriting_year",
            "province",
            "line_of_business",
        ),
    )

    policy_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    province: Mapped[str] = mapped_column(String(2))
    line_of_business: Mapped[str] = mapped_column(String(64))
    underwriting_year: Mapped[int] = mapped_column(Integer)
    written_premium: Mapped[float] = mapped_column(Numeric(14, 2, asdecimal=False))


class Exposure(Base):
    __tablename__ = "exposure"
    __table_args__ = (
        CheckConstraint("exposure_units > 0", name="ck_exposure_units_positive"),
    )

    exposure_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    policy_id: Mapped[str] = mapped_column(ForeignKey("policies.policy_id"), index=True)
    exposure_year: Mapped[int] = mapped_column(Integer)
    exposure_units: Mapped[float] = mapped_column(Numeric(8, 4, asdecimal=False))


class Claim(Base):
    __tablename__ = "claims"
    __table_args__ = (
        CheckConstraint("paid_amount >= 0", name="ck_claims_paid_non_negative"),
    )

    claim_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    policy_id: Mapped[str] = mapped_column(ForeignKey("policies.policy_id"), index=True)
    claim_year: Mapped[int] = mapped_column(Integer)
    claim_type: Mapped[str] = mapped_column(String(64))
    paid_amount: Mapped[float] = mapped_column(Numeric(14, 2, asdecimal=False))
