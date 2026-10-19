from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.platform.db import Base

REGIONS = ("northeast", "southeast", "midwest", "west")
TYPES = ("goodwill", "dispute")
STATUSES = ("requested", "pending_second_approval", "approved", "paid", "rejected")
OPEN_STATUSES = ("requested", "pending_second_approval")


class Refund(Base):
    __tablename__ = "refunds"
    __table_args__ = (
        Index("ix_refunds_region_status", "region", "status"),
        Index("ix_refunds_status_created", "status", "created_at"),
        Index("ix_refunds_status_deadline", "status", "deadline_on"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(String(24), unique=True)
    customer_name: Mapped[str] = mapped_column(String(120))
    card_last4: Mapped[str] = mapped_column(String(4))  # only the last 4 digits are ever stored
    amount_cents: Mapped[int] = mapped_column(Integer, index=True)
    type: Mapped[str] = mapped_column(String(8), index=True)
    reason: Mapped[str] = mapped_column(Text)
    reported_on: Mapped[str | None] = mapped_column(String(10))  # disputes: the day the customer reported it
    deadline_on: Mapped[str | None] = mapped_column(String(10))  # disputes: reported_on + 10 business days
    region: Mapped[str] = mapped_column(String(16), index=True)
    status: Mapped[str] = mapped_column(String(24), index=True, default="requested")
    requester_id: Mapped[str] = mapped_column(String(64), index=True)
    rejecter_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[str] = mapped_column(String(32), index=True)
    updated_at: Mapped[str] = mapped_column(String(32), index=True)
    approved_at: Mapped[str | None] = mapped_column(String(32))
    paid_at: Mapped[str | None] = mapped_column(String(32))
    rejected_at: Mapped[str | None] = mapped_column(String(32))
    version: Mapped[int] = mapped_column(Integer, default=1)
    approvals: Mapped[list[RefundApproval]] = relationship(
        cascade="all, delete-orphan", lazy="selectin", order_by="RefundApproval.id"
    )


class RefundApproval(Base):
    __tablename__ = "refund_approvals"

    id: Mapped[int] = mapped_column(primary_key=True)
    refund_id: Mapped[int] = mapped_column(ForeignKey("refunds.id"), index=True)
    approver_id: Mapped[str] = mapped_column(String(64))
    approved_at: Mapped[str] = mapped_column(String(32))
