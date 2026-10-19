from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from backend.apps.refunds import service
from backend.apps.refunds.models import Refund
from backend.apps.refunds.service import POLICY, RECORD_TYPE
from backend.platform import audit
from backend.platform.auth import User, current_user
from backend.platform.db import get_session
from backend.platform.paging import PageParams, page_params, paginate

router = APIRouter(prefix="/refunds", tags=["refunds"])

# The steps shown on the history timeline to roles without audit.read.
WORKFLOW_ACTIONS = ("refund.request", "refund.approve", "refund.reject", "refund.pay")

SORT_COLUMNS = {
    "reference": Refund.reference,
    "amount_cents": Refund.amount_cents,
    "type": Refund.type,
    "region": Refund.region,
    "status": Refund.status,
    # most urgent first; goodwill refunds have no deadline and sort after every dispute
    "deadline_on": func.coalesce(Refund.deadline_on, "9999-12-31"),
    "created_at": Refund.created_at,
    "updated_at": Refund.updated_at,
}


def _filtered(
    user: User, *, status: str | None, type: str | None, region: str | None, q: str | None
) -> Select:
    stmt = POLICY.scoped(user, select(Refund), Refund)
    if status:
        statuses = [part.strip() for part in status.split(",") if part.strip()]
        stmt = (
            stmt.where(Refund.status.in_(statuses))
            if len(statuses) > 1
            else stmt.where(Refund.status == statuses[0])
        )
    if type:
        stmt = stmt.where(Refund.type == type)
    if region:
        stmt = stmt.where(Refund.region == region)
    if q:
        needle = q.strip().upper()
        if needle.isdigit():
            needle = f"TEST-RFD-{int(needle):06d}"
        stmt = (
            stmt.where(Refund.reference.like(f"{needle}%"))
            if needle.startswith("TEST-")
            else stmt.where(Refund.reference.like(f"%{needle}%"))
        )
    return stmt


@router.get("")
def list_refunds(
    status: str | None = Query(
        None, description="One status or a comma-separated list, e.g. requested,pending_second_approval"
    ),
    type: str | None = None,
    region: str | None = None,
    q: str | None = None,
    params: PageParams = Depends(page_params),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    POLICY.require(user, "refund.read")
    stmt = _filtered(user, status=status, type=type, region=region, q=q)
    if params.sort is None:
        # work to do first: oldest requests at the top unless the caller picks a sort
        params = PageParams(page=params.page, page_size=params.page_size, sort="created_at", order="asc")
    page = paginate(
        session, stmt, params, sort_columns=SORT_COLUMNS, default_sort="created_at", tiebreaker=Refund.id
    )
    return page.to_dict(lambda refund: service.serialize(user, refund))


@router.get("/count")
def count_refunds(
    status: str | None = None,
    type: str | None = None,
    region: str | None = None,
    q: str | None = None,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> dict[str, int]:
    POLICY.require(user, "refund.read")
    stmt = _filtered(user, status=status, type=type, region=region, q=q)
    return {"count": session.scalar(select(func.count()).select_from(stmt.subquery())) or 0}


@router.get("/{refund_id}")
def get_refund(
    refund_id: int, user: User = Depends(current_user), session: Session = Depends(get_session)
) -> dict[str, Any]:
    POLICY.require(user, "refund.read")
    return service.serialize(user, service.get_scoped(session, user, refund_id))


@router.get("/{refund_id}/history")
def refund_history(
    refund_id: int, user: User = Depends(current_user), session: Session = Depends(get_session)
) -> dict[str, Any]:
    POLICY.require(user, "refund.read")
    refund = service.get_scoped(session, user, refund_id)
    return audit.record_history(
        session,
        POLICY,
        user,
        record_type=RECORD_TYPE,
        record_id=refund.reference,
        workflow_actions=WORKFLOW_ACTIONS,
    )


class RequestBody(BaseModel):
    customer_name: str = Field(min_length=1, max_length=120)
    card_last4: str = Field(
        pattern=r"^\d{4}$", description="Only the last 4 digits; never a full card number"
    )
    amount_cents: int = Field(gt=0, le=10_000_000_00)
    type: str
    reason: str = Field(min_length=1, max_length=2000)
    reported_on: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    region: str


class VersionBody(BaseModel):
    version: int


@router.post("", status_code=201)
def request_refund(
    body: RequestBody,
    request: Request,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    POLICY.require(user, "refund.request")
    refund = service.request(
        session,
        user,
        customer_name=body.customer_name,
        card_last4=body.card_last4,
        amount_cents=body.amount_cents,
        type=body.type,
        reason=body.reason,
        reported_on=body.reported_on,
        region=body.region,
        request_id=request.state.request_id,
    )
    return service.serialize(user, refund)


@router.post("/{refund_id}/approve")
def approve_refund(
    refund_id: int,
    body: VersionBody,
    request: Request,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    POLICY.require(user, "refund.approve")
    refund = service.approve(
        session, user, refund_id, version=body.version, request_id=request.state.request_id
    )
    return service.serialize(user, refund)


@router.post("/{refund_id}/reject")
def reject_refund(
    refund_id: int,
    body: VersionBody,
    request: Request,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    POLICY.require(user, "refund.reject")
    refund = service.reject(
        session, user, refund_id, version=body.version, request_id=request.state.request_id
    )
    return service.serialize(user, refund)


@router.post("/{refund_id}/pay")
def pay_refund(
    refund_id: int,
    body: VersionBody,
    request: Request,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    POLICY.require(user, "refund.pay")
    refund = service.pay(session, user, refund_id, version=body.version, request_id=request.state.request_id)
    return service.serialize(user, refund)
