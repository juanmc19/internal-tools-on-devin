from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.platform import audit
from backend.platform.auth import User, current_user
from backend.platform.db import get_session
from backend.platform.paging import PageParams, page_params, paginate

router = APIRouter(tags=["audit"])

AUDIT_SORT = {"id": audit.AuditEntry.id, "ts": audit.AuditEntry.ts, "action": audit.AuditEntry.action}


def _authorize(request: Request, user: User, app_key: str) -> None:
    manifest = request.app.state.registry.require(app_key)
    manifest.policy.require(user, "audit.read")


@router.get("/audit")
def list_audit(
    request: Request,
    app: str = Query(..., description="App key, e.g. kyc"),
    record_id: str | None = Query(None),
    action: str | None = Query(None),
    actor_id: str | None = Query(None),
    params: PageParams = Depends(page_params),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    _authorize(request, user, app)
    stmt = select(audit.AuditEntry).where(audit.AuditEntry.app == app)
    if record_id:
        stmt = stmt.where(audit.AuditEntry.record_id == record_id)
    if action:
        stmt = stmt.where(audit.AuditEntry.action == action)
    if actor_id:
        stmt = stmt.where(audit.AuditEntry.actor_id == actor_id)
    if params.sort is None:
        params = PageParams(page=params.page, page_size=params.page_size, sort="id", order="desc")
    page = paginate(
        session, stmt, params, sort_columns=AUDIT_SORT, default_sort="id", tiebreaker=audit.AuditEntry.id
    )
    return page.to_dict(lambda e: e.to_dict())


@router.get("/audit/verify")
def verify_audit(
    request: Request,
    app: str = Query(...),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    _authorize(request, user, app)
    return audit.verify(session)
