from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from backend.platform.db import get_read_session

router = APIRouter(tags=["health"])


@router.get("/health")
def health(request: Request, session: Session = Depends(get_read_session)) -> dict[str, Any]:
    registry = request.app.state.registry
    chain = request.app.state.audit_chain.status(session)
    apps = []
    for manifest in registry.all():
        apps.append(
            {
                "key": manifest.key,
                "name": manifest.name,
                "owner_team": manifest.owner_team,
                "description": manifest.description,
                "web_path": manifest.web_path,
                "status": "ok",
                "record_count": manifest.count_records(session),
            }
        )
    return {
        "status": "ok",
        "env": request.app.state.settings.app_env,
        "apps": apps,
        "audit": {"entries": chain["entries"], "chain_ok": chain["ok"]},
    }
