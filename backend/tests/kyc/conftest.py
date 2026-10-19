from __future__ import annotations

import sqlite3
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.apps.kyc.app import MANIFEST
from backend.apps.kyc.models import Case
from backend.apps.kyc.seed import PERSONAS, seed
from backend.platform.app import create_app
from backend.platform.auth import RoleAssignment, upsert_user
from backend.platform.settings import Settings
from backend.tests.conftest import local_client

ANA, BRUNO, CAMILA, DIEGO, ELENA = (p[0] for p in PERSONAS)

# reference, country, applicant, dob, id number, address, status, assignee, recommender, recommendation
CASES = [
    (
        "TEST-KYC-000001",
        "MX",
        "Ana Ruiz",
        "1987-04-12",
        "MX123456789",
        "12 Av. Reforma, Ciudad de México",
        "new",
    ),
    (
        "TEST-KYC-000002",
        "MX",
        "Bo Chen",
        "1990-11-03",
        "MX987654321",
        "3 Calle Luna, Monterrey",
        "recommended",
    ),
    ("TEST-KYC-000003", "CO", "Cy Diaz", "1975-01-30", "CO111222333", "8 Carrera 7, Bogotá", "new"),
    ("TEST-KYC-000004", "BR", "Di Evans", "2001-07-07", "BR333444555", "1 Rua das Flores, São Paulo", "new"),
    (
        "TEST-KYC-000005",
        "BR",
        "Ed Fox",
        "1999-12-25",
        "BR555666777",
        "9 Rua das Flores, Rio de Janeiro",
        "in_review",
    ),
    ("TEST-KYC-000006", "AR", "Fe Gil", "1980-02-02", "AR777888999", "5 Av. Libertador, Córdoba", "new"),
    ("TEST-KYC-000007", "CL", "Gi Hall", "1965-06-15", "CL101010101", "7 Calle Sol, Santiago", "new"),
    ("TEST-KYC-000008", "PE", "Hu Ito", "1995-09-09", "PE202020202", "2 Jr. Unión, Lima", "new"),
]


def small_seed(session) -> None:
    for uid, name, role, attrs in PERSONAS:
        upsert_user(
            session, id=uid, name=name, roles=[RoleAssignment(app="kyc", role=role, attributes=attrs)]
        )
    upsert_user(
        session, id="TEST-USR-GHOST", name="Gus Ghost", roles=[RoleAssignment(app="kyc", role="phantom")]
    )
    for i, (ref, country, name, dob, idn, addr, status) in enumerate(CASES, start=1):
        case = Case(
            id=i,
            reference=ref,
            country=country,
            applicant_name=name,
            date_of_birth=dob,
            id_number=idn,
            address=addr,
            risk="low",
            screening_result="clear",
            status=status,
            created_at="2026-10-01T00:00:00Z",
            updated_at="2026-10-01T00:00:00Z",
            version=1,
        )
        if status == "in_review":
            case.assignee_id, case.claimed_at, case.version = BRUNO, "2026-10-02T00:00:00Z", 2
        if status == "recommended":
            case.assignee_id = case.recommender_id = CAMILA
            case.recommendation, case.recommendation_note = "approve", "Looks fine."
            case.claimed_at = case.recommended_at = "2026-10-02T00:00:00Z"
            case.version = 3
        session.add(case)


def build_app(path, env: str = "dev", full: bool = False):
    settings = Settings(app_env=env, database_url=f"sqlite:///{path}")
    app = create_app(settings, [MANIFEST])
    with app.state.db.session() as session:
        (seed if full else small_seed)(session)
        session.commit()
    return app


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "kyc.db"


@pytest.fixture
def app(db_path):
    return build_app(db_path)


@pytest.fixture
def client(app) -> Iterator[TestClient]:
    with local_client(app) as c:
        yield c


@pytest.fixture
def raw(db_path) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(db_path)
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def big_client(tmp_path_factory) -> Iterator[TestClient]:
    """The real 50,000-case seed, built once per module (about 3 s)."""
    app = build_app(tmp_path_factory.mktemp("big") / "kyc.db", full=True)
    with local_client(app) as c:
        yield c


def as_user(user_id: str) -> dict[str, str]:
    return {"X-Dev-User": user_id}
