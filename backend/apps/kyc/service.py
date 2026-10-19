"""Every KYC state change is one function here: scoped lookup, version check, transition check, separation of
duties, the change, its audit entry, commit. Nothing persists unless all of it succeeds."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.apps.kyc.models import OUTCOMES, Case
from backend.platform import audit, masking
from backend.platform.auth import User
from backend.platform.errors import ApiError, not_found
from backend.platform.policy import Policy

POLICY = Policy.load(Path(__file__).with_name("policy.yaml"))
RECORD_TYPE = "case"
LIST_PROFILE = "standard"  # queue rows are masked for every role; the detail is masked by role

PII_FIELDS = ("applicant_name", "date_of_birth", "id_number", "address")


def to_record(case: Case) -> dict[str, Any]:
    return {
        "id": case.id,
        "reference": case.reference,
        "applicant_name": case.applicant_name,
        "date_of_birth": case.date_of_birth,
        "id_number": case.id_number,
        "address": case.address,
        "city": case.city,
        "country": case.country,
        "risk": case.risk,
        "screening_result": case.screening_result,
        "status": case.status,
        "assignee_id": case.assignee_id,
        "recommender_id": case.recommender_id,
        "recommendation": case.recommendation,
        "recommendation_note": case.recommendation_note,
        "decider_id": case.decider_id,
        "decision": case.decision,
        "created_at": case.created_at,
        "updated_at": case.updated_at,
        "claimed_at": case.claimed_at,
        "recommended_at": case.recommended_at,
        "decided_at": case.decided_at,
        "version": case.version,
    }


def serialize_row(case: Case) -> dict[str, Any]:
    """Queue row: masked with the standard profile for everyone; no role sees PII in a list."""
    record = to_record(case)
    for field_name, strategy in POLICY.profiles[LIST_PROFILE].items():
        record[field_name] = masking.apply(strategy, record[field_name])
    record["masked"] = True
    return record


def serialize_detail(user: User, case: Case) -> dict[str, Any]:
    record = POLICY.mask(user, to_record(case))
    record["masked"] = POLICY.is_masked(user)
    return record


def get_scoped(session: Session, user: User, case_id: int) -> Case:
    stmt = POLICY.scoped(user, select(Case).where(Case.id == case_id), Case)
    case = session.scalars(stmt).first()
    if case is None:
        raise not_found("case")
    return case


def read_detail(
    session: Session, user: User, case_id: int, *, unmasked: bool, request_id: str | None
) -> Case:
    """PRIV-3: a masked role asking for unmasked data is refused; a permitted unmasked read is audited."""
    case = get_scoped(session, user, case_id)
    if POLICY.is_masked(user):
        if unmasked:
            raise ApiError(
                403,
                "PII_MASKED_FOR_ROLE",
                "Your role sees masked applicant data.",
                app=POLICY.app,
                record_type=RECORD_TYPE,
                record_id=case.reference,
            )
        return case
    POLICY.require(user, "case.read_unmasked", record_type=RECORD_TYPE, record_id=case.reference)
    audit.write(
        session,
        app=POLICY.app,
        actor_id=user.id,
        action="case.read_unmasked",
        record_type=RECORD_TYPE,
        record_id=case.reference,
        diff={"fields": list(PII_FIELDS)},
        request_id=request_id,
    )
    session.commit()
    return case


def _check_version(case: Case, version: int) -> None:
    if version != case.version:
        raise ApiError(
            409,
            "VERSION_CONFLICT",
            f"{case.reference} changed since you loaded it (version {case.version}). Reload and try again.",
        )


def _check_outcome(outcome: str) -> None:
    if outcome not in OUTCOMES:
        raise ApiError(400, "INVALID_OUTCOME", "Outcome must be 'approve' or 'reject'.")


def claim(session: Session, user: User, case_id: int, *, version: int, request_id: str | None = None) -> Case:
    case = get_scoped(session, user, case_id)
    _check_version(case, version)
    if case.status != "new":
        raise ApiError(
            409, "INVALID_TRANSITION", f"Only new cases can be claimed; this one is {case.status}."
        )
    now = audit.now_iso()
    case.status, case.assignee_id, case.claimed_at, case.updated_at = "in_review", user.id, now, now
    case.version += 1
    audit.write(
        session,
        app=POLICY.app,
        actor_id=user.id,
        action="case.claim",
        record_type=RECORD_TYPE,
        record_id=case.reference,
        diff={"status": {"from": "new", "to": "in_review"}, "assignee_id": {"from": None, "to": user.id}},
        request_id=request_id,
        ts=now,
    )
    session.commit()
    return case


def recommend(
    session: Session,
    user: User,
    case_id: int,
    *,
    outcome: str,
    note: str,
    version: int,
    request_id: str | None = None,
) -> Case:
    _check_outcome(outcome)
    case = get_scoped(session, user, case_id)
    _check_version(case, version)
    if case.status != "in_review":
        raise ApiError(
            409, "INVALID_TRANSITION", f"Only cases in review can be recommended; this one is {case.status}."
        )
    if case.assignee_id != user.id:
        raise ApiError(
            403,
            "NOT_ASSIGNEE",
            "Only the assignee can recommend this case. Claim it first.",
            app=POLICY.app,
            record_type=RECORD_TYPE,
            record_id=case.reference,
        )
    note = note.strip()
    if not note:
        raise ApiError(400, "NOTE_REQUIRED", "A recommendation needs a note.")
    now = audit.now_iso()
    case.status, case.recommender_id, case.recommendation = "recommended", user.id, outcome
    case.recommendation_note, case.recommended_at, case.updated_at = note, now, now
    case.version += 1
    audit.write(
        session,
        app=POLICY.app,
        actor_id=user.id,
        action="case.recommend",
        record_type=RECORD_TYPE,
        record_id=case.reference,
        diff={
            "status": {"from": "in_review", "to": "recommended"},
            "recommendation": {"from": None, "to": outcome},
            "recommendation_note": {"changed": True},
        },
        request_id=request_id,
        ts=now,
    )
    session.commit()
    return case


def decide(
    session: Session, user: User, case_id: int, *, outcome: str, version: int, request_id: str | None = None
) -> Case:
    _check_outcome(outcome)
    case = get_scoped(session, user, case_id)
    _check_version(case, version)
    if case.status != "recommended":
        raise ApiError(
            409, "INVALID_TRANSITION", f"Only recommended cases can be decided; this one is {case.status}."
        )
    POLICY.check_separation("decide", user.id, case, record_type=RECORD_TYPE, record_id=case.reference)
    now = audit.now_iso()
    final = "approved" if outcome == "approve" else "rejected"
    case.status, case.decider_id, case.decision, case.decided_at, case.updated_at = (
        final,
        user.id,
        outcome,
        now,
        now,
    )
    case.version += 1
    audit.write(
        session,
        app=POLICY.app,
        actor_id=user.id,
        action="case.decide",
        record_type=RECORD_TYPE,
        record_id=case.reference,
        diff={"status": {"from": "recommended", "to": final}, "decision": {"from": None, "to": outcome}},
        request_id=request_id,
        ts=now,
    )
    session.commit()
    return case
