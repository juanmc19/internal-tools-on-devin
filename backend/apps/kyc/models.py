from __future__ import annotations

from sqlalchemy import Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.platform.db import Base

COUNTRIES = ("MX", "CO", "BR", "AR", "CL", "PE")
RISKS = ("low", "medium", "high")
SCREENING_RESULTS = ("clear", "possible_match", "match")
STATUSES = ("new", "in_review", "recommended", "approved", "rejected")
OUTCOMES = ("approve", "reject")


class Case(Base):
    __tablename__ = "kyc_cases"
    __table_args__ = (
        Index("ix_kyc_cases_country_status", "country", "status"),
        Index("ix_kyc_cases_status_updated", "status", "updated_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(String(24), unique=True)
    applicant_name: Mapped[str] = mapped_column(String(120))
    date_of_birth: Mapped[str] = mapped_column(String(10))
    id_number: Mapped[str] = mapped_column(String(32))
    address: Mapped[str] = mapped_column(String(200))
    city: Mapped[str] = mapped_column(String(80))
    country: Mapped[str] = mapped_column(String(2), index=True)
    risk: Mapped[str] = mapped_column(String(8), index=True)
    screening_result: Mapped[str] = mapped_column(String(16), index=True)
    status: Mapped[str] = mapped_column(String(16), index=True, default="new")
    assignee_id: Mapped[str | None] = mapped_column(String(64), index=True)
    recommender_id: Mapped[str | None] = mapped_column(String(64))
    recommendation: Mapped[str | None] = mapped_column(String(8))
    recommendation_note: Mapped[str | None] = mapped_column(Text)
    decider_id: Mapped[str | None] = mapped_column(String(64))
    decision: Mapped[str | None] = mapped_column(String(8))
    created_at: Mapped[str] = mapped_column(String(32))
    updated_at: Mapped[str] = mapped_column(String(32), index=True)
    claimed_at: Mapped[str | None] = mapped_column(String(32))
    recommended_at: Mapped[str | None] = mapped_column(String(32))
    decided_at: Mapped[str | None] = mapped_column(String(32))
    version: Mapped[int] = mapped_column(Integer, default=1)
