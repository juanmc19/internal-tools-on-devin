"""A minimal app built only from foundation helpers. It has no app-specific control logic: every rule it
obeys comes from tests/testapp/policy.yaml."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import ForeignKey, Integer, Numeric, String, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from backend.platform import audit
from backend.platform.auth import User, current_user
from backend.platform.db import Base, get_session
from backend.platform.errors import ApiError, not_found
from backend.platform.paging import PageParams, page_params, paginate
from backend.platform.policy import Policy
from backend.platform.registry import AppManifest

POLICY = Policy.load(Path(__file__).with_name("policy.yaml"))


class Widget(Base):
    __tablename__ = "test_widgets"

    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(String(32), unique=True)
    region: Mapped[str] = mapped_column(String(16), index=True)
    owner_name: Mapped[str] = mapped_column(String(120))
    id_number: Mapped[str] = mapped_column(String(32))
    address: Mapped[str] = mapped_column(String(200))
    born_on: Mapped[str] = mapped_column(String(10))
    amount: Mapped[float] = mapped_column(Numeric(12, 2))
    status: Mapped[str] = mapped_column(String(32), default="requested")
    requested_by: Mapped[str | None] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(Integer, default=1)
    approvals: Mapped[list[WidgetApproval]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class WidgetApproval(Base):
    __tablename__ = "test_widget_approvals"

    id: Mapped[int] = mapped_column(primary_key=True)
    widget_id: Mapped[int] = mapped_column(ForeignKey("test_widgets.id"))
    approver_id: Mapped[str] = mapped_column(String(64))


def serialize(policy: Policy, user: User, widget: Widget) -> dict[str, Any]:
    record = {
        "id": widget.id,
        "reference": widget.reference,
        "region": widget.region,
        "owner_name": widget.owner_name,
        "id_number": widget.id_number,
        "address": widget.address,
        "born_on": widget.born_on,
        "amount": float(widget.amount),
        "status": widget.status,
        "requested_by": widget.requested_by,
        "approvals": [a.approver_id for a in widget.approvals],
        "version": widget.version,
    }
    return policy.mask(user, record)


def get_scoped(session: Session, user: User, widget_id: int) -> Widget:
    stmt = POLICY.scoped(user, select(Widget).where(Widget.id == widget_id), Widget)
    widget = session.scalars(stmt).first()
    if widget is None:
        raise not_found("widget")
    return widget


def approve(session: Session, user: User, widget_id: int, *, request_id: str | None = None) -> Widget:
    """One transaction: transition check, separation of duties, state change, audit entry, commit."""
    widget = get_scoped(session, user, widget_id)
    if widget.status not in ("requested", "pending"):
        raise ApiError(409, "INVALID_TRANSITION", f"Cannot approve a widget that is {widget.status}.")
    POLICY.check_separation("approve", user.id, widget, record_type="widget", record_id=widget.reference)
    widget.approvals.append(WidgetApproval(approver_id=user.id))
    approver_ids = [a.approver_id for a in widget.approvals]
    before = widget.status
    widget.status = "approved" if POLICY.approvals_complete("approve", widget, approver_ids) else "pending"
    widget.version += 1
    audit.write(
        session,
        app=POLICY.app,
        actor_id=user.id,
        action="widget.approve",
        record_type="widget",
        record_id=widget.reference,
        diff={"status": {"from": before, "to": widget.status}, "approvals": len(approver_ids)},
        request_id=request_id,
    )
    session.commit()
    return widget


def rename_then_fail(session: Session, user: User, widget_id: int) -> None:
    """A change that writes its audit entry and then fails before commit; nothing may persist."""
    widget = get_scoped(session, user, widget_id)
    widget.status = "broken"
    audit.write(session, app=POLICY.app, actor_id=user.id, action="widget.break", record_id=widget.reference)
    raise RuntimeError("simulated failure after audit write")


router = APIRouter(prefix="/testapp", tags=["testapp"])


@router.get("/widgets")
def list_widgets(
    region: str | None = None,
    params: PageParams = Depends(page_params),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    POLICY.require(user, "widget.read")
    stmt = POLICY.scoped(user, select(Widget), Widget)
    if region:
        stmt = stmt.where(Widget.region == region)
    page = paginate(
        session,
        stmt,
        params,
        sort_columns={"id": Widget.id, "amount": Widget.amount, "reference": Widget.reference},
        default_sort="id",
        tiebreaker=Widget.id,
    )
    return page.to_dict(lambda w: serialize(POLICY, user, w))


@router.get("/widgets/count")
def count_widgets(user: User = Depends(current_user), session: Session = Depends(get_session)) -> dict:
    POLICY.require(user, "widget.read")
    stmt = POLICY.scoped(user, select(func.count()).select_from(Widget), Widget)
    return {"count": session.scalar(stmt) or 0}


@router.get("/widgets/{widget_id}")
def get_widget(
    widget_id: int,
    unmasked: bool = False,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    POLICY.require(user, "widget.read")
    widget = get_scoped(session, user, widget_id)
    if unmasked and POLICY.is_masked(user):
        raise ApiError(
            403,
            "PII_MASKED_FOR_ROLE",
            "Your role sees masked data.",
            app=POLICY.app,
            record_type="widget",
            record_id=widget.reference,
        )
    return serialize(POLICY, user, widget)


@router.post("/widgets/{widget_id}/approve")
def approve_widget(
    widget_id: int,
    request: Request,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    POLICY.require(user, "widget.approve")
    widget = approve(session, user, widget_id, request_id=request.state.request_id)
    return serialize(POLICY, user, widget)


def count_records(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(Widget)) or 0


MANIFEST = AppManifest(
    key="testapp",
    name="Test App",
    owner_team="Platform",
    description="Test-only app proving the foundation enforces policy.yaml.",
    policy=POLICY,
    router=router,
    web_path="/testapp",
    count_records=count_records,
    record_type="widget",
    record_model=Widget,
)
