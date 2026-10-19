from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.apps.kyc.app import MANIFEST as KYC
from backend.apps.kyc.seed import PERSONAS as KYC_PERSONAS
from backend.apps.refunds import business_days
from backend.apps.refunds.app import MANIFEST
from backend.apps.refunds.models import Refund, RefundApproval
from backend.apps.refunds.seed import PERSONAS, seed
from backend.platform.app import create_app
from backend.platform.auth import RoleAssignment, upsert_user
from backend.platform.settings import Settings

GABRIELA, HUGO, INES, JAVIER, KARLA, ELENA = (p[0] for p in PERSONAS)
T0 = "2026-10-01T00:00:00Z"

# id, region, customer, last4, amount_cents, type, status, requester
REFUNDS = [
    (1, "northeast", "Ana Ruiz", "4242", 20_000, "goodwill", "requested", GABRIELA),
    (2, "northeast", "Bo Chen", "1881", 750_000, "dispute", "requested", GABRIELA),
    (3, "midwest", "Cy Diaz", "0005", 5_000, "goodwill", "requested", HUGO),
    (4, "west", "Di Evans", "9999", 900_000, "goodwill", "requested", INES),
    (5, "southeast", "Ed Fox", "1234", 30_000, "goodwill", "approved", GABRIELA),
    (6, "west", "Fe Gil", "5678", 12_000, "dispute", "paid", HUGO),
]


def small_seed(session) -> None:
    for uid, name, role, attrs in KYC_PERSONAS:
        upsert_user(
            session, id=uid, name=name, roles=[RoleAssignment(app="kyc", role=role, attributes=attrs)]
        )
    for uid, name, role, attrs in PERSONAS:
        upsert_user(
            session, id=uid, name=name, roles=[RoleAssignment(app="refunds", role=role, attributes=attrs)]
        )
    upsert_user(
        session, id="TEST-USR-GHOST", name="Gus Ghost", roles=[RoleAssignment(app="refunds", role="phantom")]
    )
    for rid, region, name, last4, amount, rtype, status, requester in REFUNDS:
        refund = Refund(
            id=rid,
            reference=f"TEST-RFD-{rid:06d}",
            region=region,
            customer_name=name,
            card_last4=last4,
            amount_cents=amount,
            type=rtype,
            reason="Seeded for tests.",
            reported_on="2026-09-20" if rtype == "dispute" else None,
            deadline_on=business_days.deadline_for("2026-09-20") if rtype == "dispute" else None,
            status=status,
            requester_id=requester,
            created_at=T0,
            updated_at=T0,
            version=1,
        )
        if status in ("approved", "paid"):
            refund.approvals.append(RefundApproval(approver_id=INES, approved_at=T0))
            refund.approved_at, refund.version = T0, 2
        if status == "paid":
            refund.paid_at, refund.version = T0, 3
        session.add(refund)


def build_app(path, env: str = "dev", full: bool = False):
    settings = Settings(app_env=env, database_url=f"sqlite:///{path}")
    app = create_app(settings, [KYC, MANIFEST])
    with app.state.db.session() as session:
        (seed if full else small_seed)(session)
        session.commit()
    return app


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "refunds.db"


@pytest.fixture
def client(db_path) -> Iterator[TestClient]:
    with TestClient(build_app(db_path)) as c:
        yield c


@pytest.fixture(scope="module")
def big_client(tmp_path_factory) -> Iterator[TestClient]:
    """The real 20,000-refund seed, built once per module."""
    with TestClient(build_app(tmp_path_factory.mktemp("big") / "refunds.db", full=True)) as c:
        yield c


def as_user(user_id: str) -> dict[str, str]:
    return {"X-Dev-User": user_id}
