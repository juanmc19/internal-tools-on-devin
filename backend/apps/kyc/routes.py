from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from backend.apps.kyc import service
from backend.apps.kyc.models import Case
from backend.apps.kyc.service import POLICY, RECORD_TYPE
from backend.platform import audit
from backend.platform.auth import User, current_user
from backend.platform.db import get_session
from backend.platform.paging import PageParams, page_params, paginate

router = APIRouter(prefix="/kyc", tags=["kyc"])

# The steps shown on the history timeline to roles without audit.read.
WORKFLOW_ACTIONS = ("case.claim", "case.recommend", "case.decide")

SORT_COLUMNS = {
    "reference": Case.reference,
    "country": Case.country,
    "risk": Case.risk,
    "screening_result": Case.screening_result,
    "status": Case.status,
    "created_at": Case.created_at,
    "updated_at": Case.updated_at,
}


def _filtered(
    user: User,
    *,
    status: str | None,
    country: str | None,
    risk: str | None,
    screening_result: str | None,
    q: str | None,
    assignee_id: str | None,
) -> Select:
    stmt = POLICY.scoped(user, select(Case), Case)
    if status:
        statuses = [part.strip() for part in status.split(",") if part.strip()]
        stmt = (
            stmt.where(Case.status.in_(statuses))
            if len(statuses) > 1
            else stmt.where(Case.status == statuses[0])
        )
    if country:
        stmt = stmt.where(Case.country == country)
    if risk:
        stmt = stmt.where(Case.risk == risk)
    if screening_result:
        stmt = stmt.where(Case.screening_result == screening_result)
    if assignee_id:
        stmt = stmt.where(Case.assignee_id == assignee_id)
    if q:
        needle = q.strip().upper()
        if needle.isdigit():
            needle = f"TEST-KYC-{int(needle):06d}"
        stmt = (
            stmt.where(Case.reference.like(f"{needle}%"))
            if needle.startswith("TEST-")
            else stmt.where(Case.reference.like(f"%{needle}%"))
        )
    return stmt


@router.get("/cases")
def list_cases(
    status: str | None = Query(None, description="One status or a comma-separated list, e.g. new,in_review"),
    country: str | None = None,
    risk: str | None = None,
    screening_result: str | None = None,
    q: str | None = None,
    assignee_id: str | None = None,
    params: PageParams = Depends(page_params),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    POLICY.require(user, "case.read")
    stmt = _filtered(
        user,
        status=status,
        country=country,
        risk=risk,
        screening_result=screening_result,
        q=q,
        assignee_id=assignee_id,
    )
    if params.sort is None:
        # newest activity first unless the caller picks a sort
        params = PageParams(page=params.page, page_size=params.page_size, sort="updated_at", order="desc")
    page = paginate(
        session, stmt, params, sort_columns=SORT_COLUMNS, default_sort="updated_at", tiebreaker=Case.id
    )
    return page.to_dict(service.serialize_row)


@router.get("/cases/count")
def count_cases(
    status: str | None = None,
    country: str | None = None,
    risk: str | None = None,
    screening_result: str | None = None,
    q: str | None = None,
    assignee_id: str | None = None,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> dict[str, int]:
    POLICY.require(user, "case.read")
    stmt = _filtered(
        user,
        status=status,
        country=country,
        risk=risk,
        screening_result=screening_result,
        q=q,
        assignee_id=assignee_id,
    )
    return {"count": session.scalar(select(func.count()).select_from(stmt.subquery())) or 0}


@router.get("/cases/{case_id}")
def get_case(
    case_id: int,
    request: Request,
    unmasked: bool = False,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    POLICY.require(user, "case.read")
    case = service.read_detail(session, user, case_id, unmasked=unmasked, request_id=request.state.request_id)
    return service.serialize_detail(user, case)


@router.get("/cases/{case_id}/history")
def case_history(
    case_id: int,
    params: PageParams = Depends(page_params),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    POLICY.require(user, "case.read")
    case = service.get_scoped(session, user, case_id)
    return audit.record_history(
        session,
        POLICY,
        user,
        record_type=RECORD_TYPE,
        record_id=case.reference,
        workflow_actions=WORKFLOW_ACTIONS,
        params=params,
    )


class VersionBody(BaseModel):
    version: int


class RecommendBody(VersionBody):
    outcome: str
    note: str = Field(default="", max_length=2000)


class DecideBody(VersionBody):
    outcome: str


@router.post("/cases/{case_id}/claim")
def claim_case(
    case_id: int,
    body: VersionBody,
    request: Request,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    POLICY.require(user, "case.claim")
    case = service.claim(session, user, case_id, version=body.version, request_id=request.state.request_id)
    return service.serialize_detail(user, case)


@router.post("/cases/{case_id}/recommend")
def recommend_case(
    case_id: int,
    body: RecommendBody,
    request: Request,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    POLICY.require(user, "case.recommend")
    case = service.recommend(
        session,
        user,
        case_id,
        outcome=body.outcome,
        note=body.note,
        version=body.version,
        request_id=request.state.request_id,
    )
    return service.serialize_detail(user, case)


@router.post("/cases/{case_id}/decide")
def decide_case(
    case_id: int,
    body: DecideBody,
    request: Request,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    POLICY.require(user, "case.decide")
    case = service.decide(
        session,
        user,
        case_id,
        outcome=body.outcome,
        version=body.version,
        request_id=request.state.request_id,
    )
    return service.serialize_detail(user, case)
