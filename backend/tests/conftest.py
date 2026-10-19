from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.platform.app import create_app
from backend.platform.auth import RoleAssignment, upsert_user
from backend.platform.settings import Settings
from backend.tests.testapp.app import MANIFEST, Widget

USERS = {
    "viewer_north": ("Nora North", "viewer", {"regions": ["north"]}),
    "viewer_none": ("Nobody Scope", "viewer", {"regions": []}),
    "requester": ("Rita Request", "requester", {}),
    "manager_1": ("Mark Manager", "manager", {}),
    "manager_2": ("Mona Manager", "manager", {}),
    "ghost": ("Gus Ghost", "phantom_role", {}),
}

WIDGETS = [
    # reference, region, owner_name, id_number, address, born_on, amount, requested_by
    (
        "TEST-WID-000001",
        "north",
        "Ana Ruiz",
        "AB1234567",
        "12 Elm Street, Austin",
        "1987-04-12",
        500,
        "requester",
    ),
    (
        "TEST-WID-000002",
        "north",
        "Bo Chen",
        "CD7654321",
        "3 Rue Verte, Lyon",
        "1990-11-03",
        2500,
        "requester",
    ),
    (
        "TEST-WID-000003",
        "south",
        "Cy Diaz",
        "EF1112222",
        "8 Calle Sol, Sevilla",
        "1975-01-30",
        100,
        "manager_1",
    ),
    (
        "TEST-WID-000004",
        "south",
        "Di Evans",
        "GH3334444",
        "1 Main Road, Leeds",
        "2001-07-07",
        5000,
        "requester",
    ),
    ("TEST-WID-000005", "north", "Ed Fox", "IJ5556666", "9 High Street, York", "1999-12-25", 20, "requester"),
]


def build_app(tmp_path, env: str = "dev"):
    settings = Settings(app_env=env, database_url=f"sqlite:///{tmp_path / 'test.db'}")
    app = create_app(settings, [MANIFEST])
    with app.state.db.session() as session:
        for uid, (name, role, attrs) in USERS.items():
            upsert_user(
                session, id=uid, name=name, roles=[RoleAssignment(app="testapp", role=role, attributes=attrs)]
            )
        for ref, region, owner, idn, addr, born, amount, req in WIDGETS:
            session.add(
                Widget(
                    reference=ref,
                    region=region,
                    owner_name=owner,
                    id_number=idn,
                    address=addr,
                    city=addr.rsplit(", ", 1)[-1],
                    born_on=born,
                    amount=amount,
                    requested_by=req,
                )
            )
        session.commit()
    return app


@pytest.fixture
def app(tmp_path):
    return build_app(tmp_path)


def local_client(app, client_host: str = "127.0.0.1") -> TestClient:
    """A test client that calls the API the way `make run` is reached: from loopback, Host 127.0.0.1."""
    return TestClient(app, base_url="http://127.0.0.1", client=(client_host, 50000))


@pytest.fixture
def client(app) -> Iterator[TestClient]:
    with local_client(app) as c:
        yield c


@pytest.fixture
def prod_client(tmp_path) -> Iterator[TestClient]:
    with TestClient(build_app(tmp_path, env="prod")) as c:
        yield c


def as_user(user_id: str) -> dict[str, str]:
    return {"X-Dev-User": user_id}
