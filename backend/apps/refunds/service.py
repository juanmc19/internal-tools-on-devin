"""Every Refunds state change is one function here: scoped lookup, version check, transition check,
separation of duties, the change, its audit entry, commit. Nothing persists unless all of it succeeds."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.apps.refunds.models import OPEN_STATUSES, REGIONS, TYPES, Refund, RefundApproval
from backend.platform import audit
from backend.platform.auth import User
from backend.platform.errors import ApiError, not_found
from backend.platform.policy import Policy

POLICY = Policy.load(Path(__file__).with_name("policy.yaml"))
RECORD_TYPE = "refund"
STEP = "approve"


def to_record(refund: Refund) -> dict[str, Any]:
    return {
        "id": refund.id,
        "reference": refund.reference,
        "customer_name": refund.customer_name,
        "card_last4": refund.card_last4,
        "amount_cents": refund.amount_cents,
        "type": refund.type,
        "reason": refund.reason,
        "reported_on": refund.reported_on,
        "region": refund.region,
        "status": refund.status,
        "requester_id": refund.requester_id,
        "rejecter_id": refund.rejecter_id,
        "approvals": [{"approver_id": a.approver_id, "approved_at": a.approved_at} for a in refund.approvals],
        "approvals_required": POLICY.required_approvals(STEP, refund),
        "created_at": refund.created_at,
        "updated_at": refund.updated_at,
        "approved_at": refund.approved_at,
        "paid_at": refund.paid_at,
        "rejected_at": refund.rejected_at,
        "version": refund.version,
    }


def serialize(user: User, refund: Refund) -> dict[str, Any]:
    """Rows and details alike are masked by role; no endpoint returns an unmasked customer name to a
    masked role."""
    record = POLICY.mask(user, to_record(refund))
    record["masked"] = POLICY.is_masked(user)
    return record


def get_scoped(session: Session, user: User, refund_id: int) -> Refund:
    stmt = POLICY.scoped(user, select(Refund).where(Refund.id == refund_id), Refund)
    refund = session.scalars(stmt).first()
    if refund is None:
        raise not_found("refund")
    return refund


def _check_version(refund: Refund, version: int) -> None:
    if version != refund.version:
        raise ApiError(
            409,
            "VERSION_CONFLICT",
            f"{refund.reference} changed since you loaded it (version {refund.version}). Reload and retry.",
        )


def _check_region_in_scope(user: User, region: str) -> None:
    """A role scoped by region may only request refunds for its own regions."""
    role = POLICY.role_for(user)
    if role.scope_field is None:
        return
    assignment = user.role_in(POLICY.app)
    allowed = list(assignment.attributes.get(role.scope_attribute, []) or []) if assignment else []
    if region not in allowed:
        raise ApiError(
            403,
            "OUT_OF_SCOPE",
            f"You can only request refunds for your regions ({', '.join(allowed) or 'none'}).",
            app=POLICY.app,
            record_type=RECORD_TYPE,
        )


def _next_reference(session: Session) -> str:
    next_id = (session.scalar(select(func.max(Refund.id))) or 0) + 1
    return f"TEST-RFD-{next_id:06d}"


def request(
    session: Session,
    user: User,
    *,
    customer_name: str,
    card_last4: str,
    amount_cents: int,
    type: str,
    reason: str,
    reported_on: str | None,
    region: str,
    request_id: str | None = None,
) -> Refund:
    if type not in TYPES:
        raise ApiError(400, "INVALID_TYPE", "Type must be 'goodwill' or 'dispute'.")
    if region not in REGIONS:
        raise ApiError(400, "INVALID_REGION", f"Region must be one of {', '.join(REGIONS)}.")
    if amount_cents <= 0:
        raise ApiError(400, "INVALID_AMOUNT", "Amount must be greater than zero.")
    if len(card_last4) != 4 or not card_last4.isdigit():
        raise ApiError(400, "INVALID_CARD_LAST4", "Enter exactly the last 4 digits of the card.")
    customer_name, reason = customer_name.strip(), reason.strip()
    if not customer_name:
        raise ApiError(400, "NAME_REQUIRED", "A customer name is required.")
    if not reason:
        raise ApiError(400, "REASON_REQUIRED", "A refund needs a reason.")
    if type == "dispute" and not reported_on:
        raise ApiError(400, "REPORTED_ON_REQUIRED", "A dispute needs the date the customer reported it.")
    if type == "goodwill":
        reported_on = None
    _check_region_in_scope(user, region)
    now = audit.now_iso()
    refund = Refund(
        reference=_next_reference(session),
        customer_name=customer_name,
        card_last4=card_last4,
        amount_cents=amount_cents,
        type=type,
        reason=reason,
        reported_on=reported_on,
        region=region,
        status="requested",
        requester_id=user.id,
        created_at=now,
        updated_at=now,
        version=1,
    )
    session.add(refund)
    session.flush()
    audit.write(
        session,
        app=POLICY.app,
        actor_id=user.id,
        action="refund.request",
        record_type=RECORD_TYPE,
        record_id=refund.reference,
        diff={
            "status": {"from": None, "to": "requested"},
            "amount_cents": {"from": None, "to": amount_cents},
            "type": {"from": None, "to": type},
            "region": {"from": None, "to": region},
            "customer_name": {"changed": True},
            "card_last4": {"changed": True},
            "reason": {"changed": True},
        },
        request_id=request_id,
        ts=now,
    )
    session.commit()
    return refund


def approve(
    session: Session, user: User, refund_id: int, *, version: int, request_id: str | None = None
) -> Refund:
    """REP-2 / REP-3: the requester and anyone who already approved are refused (SOD_VIOLATION); the refund
    stays pending until policy.yaml says enough distinct approvers have signed."""
    refund = get_scoped(session, user, refund_id)
    _check_version(refund, version)
    if refund.status not in OPEN_STATUSES:
        raise ApiError(
            409,
            "INVALID_TRANSITION",
            f"Only requested or pending refunds can be approved; this one is {refund.status}.",
        )
    POLICY.check_separation(STEP, user.id, refund, record_type=RECORD_TYPE, record_id=refund.reference)
    now = audit.now_iso()
    before = refund.status
    refund.approvals.append(RefundApproval(approver_id=user.id, approved_at=now))
    approver_ids = [a.approver_id for a in refund.approvals]
    complete = POLICY.approvals_complete(STEP, refund, approver_ids)
    refund.status = "approved" if complete else "pending_second_approval"
    refund.approved_at = now if complete else None
    refund.updated_at = now
    refund.version += 1
    audit.write(
        session,
        app=POLICY.app,
        actor_id=user.id,
        action="refund.approve",
        record_type=RECORD_TYPE,
        record_id=refund.reference,
        diff={
            "status": {"from": before, "to": refund.status},
            "approvals": f"{len(approver_ids)} of {POLICY.required_approvals(STEP, refund)}",
        },
        request_id=request_id,
        ts=now,
    )
    session.commit()
    return refund


def reject(
    session: Session, user: User, refund_id: int, *, version: int, request_id: str | None = None
) -> Refund:
    refund = get_scoped(session, user, refund_id)
    _check_version(refund, version)
    if refund.status not in OPEN_STATUSES:
        raise ApiError(
            409,
            "INVALID_TRANSITION",
            f"Only requested or pending refunds can be rejected; this one is {refund.status}.",
        )
    now = audit.now_iso()
    before = refund.status
    refund.status, refund.rejecter_id, refund.rejected_at, refund.updated_at = "rejected", user.id, now, now
    refund.version += 1
    audit.write(
        session,
        app=POLICY.app,
        actor_id=user.id,
        action="refund.reject",
        record_type=RECORD_TYPE,
        record_id=refund.reference,
        diff={"status": {"from": before, "to": "rejected"}, "rejecter_id": {"from": None, "to": user.id}},
        request_id=request_id,
        ts=now,
    )
    session.commit()
    return refund


def pay(
    session: Session, user: User, refund_id: int, *, version: int, request_id: str | None = None
) -> Refund:
    refund = get_scoped(session, user, refund_id)
    _check_version(refund, version)
    if refund.status != "approved":
        raise ApiError(
            409, "INVALID_TRANSITION", f"Only approved refunds can be paid; this one is {refund.status}."
        )
    now = audit.now_iso()
    refund.status, refund.paid_at, refund.updated_at = "paid", now, now
    refund.version += 1
    audit.write(
        session,
        app=POLICY.app,
        actor_id=user.id,
        action="refund.pay",
        record_type=RECORD_TYPE,
        record_id=refund.reference,
        diff={"status": {"from": "approved", "to": "paid"}, "amount_cents": refund.amount_cents},
        request_id=request_id,
        ts=now,
    )
    session.commit()
    return refund
