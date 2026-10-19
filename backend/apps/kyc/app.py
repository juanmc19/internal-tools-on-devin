from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.apps.kyc.models import Case
from backend.apps.kyc.routes import router
from backend.apps.kyc.seed import seed
from backend.apps.kyc.service import POLICY, RECORD_TYPE
from backend.platform.registry import AppManifest


def count_records(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(Case)) or 0


MANIFEST = AppManifest(
    key="kyc",
    name="KYC Review Queue",
    owner_team="Financial Crime Ops",
    description="Review onboarding cases: claim, recommend, decide, with masked applicant data by role.",
    policy=POLICY,
    router=router,
    web_path="/kyc",
    count_records=count_records,
    seed=seed,
    record_type=RECORD_TYPE,
    record_model=Case,
)
