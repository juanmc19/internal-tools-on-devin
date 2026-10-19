from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.apps.refunds.models import Refund
from backend.apps.refunds.routes import router
from backend.apps.refunds.seed import seed
from backend.apps.refunds.service import POLICY, RECORD_TYPE
from backend.platform.registry import AppManifest


def count_records(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(Refund)) or 0


MANIFEST = AppManifest(
    key="refunds",
    name="Refunds Desk",
    owner_team="Payments Ops",
    description="Request, approve and pay card refunds: two approvers above $5,000, names masked by role.",
    policy=POLICY,
    router=router,
    web_path="/refunds",
    count_records=count_records,
    seed=seed,
    record_type=RECORD_TYPE,
)
