"""Request ids: a client X-Request-Id is kept only if it is a UUID (hyphens optional), else a uuid4 hex."""

import re

import pytest

from backend.platform.app import resolve_request_id
from backend.tests.conftest import as_user

GENERATED = re.compile(r"[0-9a-f]{32}")


def _approve_and_read_request_id(client, headers: dict[str, str]) -> tuple[str, str]:
    response = client.post("/testapp/widgets/1/approve", headers={**as_user("manager_1"), **headers})
    entries = client.get("/audit?app=testapp&record_id=TEST-WID-000001", headers=as_user("manager_1")).json()
    return response.headers["X-Request-Id"], entries["items"][0]["request_id"]


CLIENT_UUID = "3f2b8c1e-9d4a-4e6b-8a7c-1d2e3f4a5b6c"


def test_client_uuid_request_id_is_kept_in_header_and_audit(client):
    echoed, stored = _approve_and_read_request_id(client, {"X-Request-Id": CLIENT_UUID})
    assert echoed == stored == CLIENT_UUID


def test_missing_request_id_is_generated(client):
    echoed, stored = _approve_and_read_request_id(client, {})
    assert GENERATED.fullmatch(echoed)
    assert stored == echoed


@pytest.mark.parametrize(
    "supplied",
    [
        "a" * 65,
        "has space",
        "semi;colon",
        "under_score",
        "x/../y",
        '{"forged":true}',
        "",
        "trace-ABC-123",
        "AnaRuiz",
        "Ana-Ruiz-1987-04-12",
    ],
)
def test_invalid_client_request_id_is_replaced_in_header_and_audit(client, supplied):
    echoed, stored = _approve_and_read_request_id(client, {"X-Request-Id": supplied})
    assert echoed != supplied
    assert GENERATED.fullmatch(echoed)
    assert stored == echoed


def test_invalid_request_id_is_replaced_on_security_denied_rows(client):
    response = client.post(
        "/testapp/widgets/1/approve", headers={**as_user("viewer_north"), "X-Request-Id": "a" * 500}
    )
    assert response.status_code == 403
    entries = client.get("/audit?app=testapp&action=security.denied", headers=as_user("manager_1")).json()
    stored = entries["items"][0]["request_id"]
    assert GENERATED.fullmatch(stored)
    assert stored == response.headers["X-Request-Id"]


ACCEPTED = [CLIENT_UUID, CLIENT_UUID.upper(), CLIENT_UUID.replace("-", "")]
REJECTED = [
    "a" * 64,
    "A",
    "0-9",
    "AnaRuiz",
    "Ana-Ruiz-1987",
    CLIENT_UUID[:-1],
    CLIENT_UUID + "0",
    "{" + CLIENT_UUID + "}",
    "urn:uuid:" + CLIENT_UUID,
    "3f2b8c1e9d4a-4e6b-8a7c-1d2e3f4a5b6c",
    "3f2b8c1e-9d4a-4e6b-8a7c-1d2e3f4a5b6g",
    CLIENT_UUID + "\n",
    "abc\r\nX: y",
    "ünïcode",
    "１２３",
    None,
]


@pytest.mark.parametrize("supplied", ACCEPTED + REJECTED)
def test_resolve_request_id_accepts_only_a_uuid(supplied):
    resolved = resolve_request_id(supplied)
    if supplied in ACCEPTED:
        assert resolved == supplied
    else:
        assert GENERATED.fullmatch(resolved)
