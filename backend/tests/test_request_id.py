"""Request ids: client X-Request-Id is accepted only if it matches ^[A-Za-z0-9-]{1,64}$, else a uuid4 hex."""

import re

import pytest

from backend.platform.app import resolve_request_id
from backend.tests.conftest import as_user

GENERATED = re.compile(r"[0-9a-f]{32}")


def _approve_and_read_request_id(client, headers: dict[str, str]) -> tuple[str, str]:
    response = client.post("/testapp/widgets/1/approve", headers={**as_user("manager_1"), **headers})
    entries = client.get("/audit?app=testapp&record_id=TEST-WID-000001", headers=as_user("manager_1")).json()
    return response.headers["X-Request-Id"], entries["items"][0]["request_id"]


def test_valid_client_request_id_is_kept_in_header_and_audit(client):
    echoed, stored = _approve_and_read_request_id(client, {"X-Request-Id": "trace-ABC-123"})
    assert echoed == stored == "trace-ABC-123"


def test_missing_request_id_is_generated(client):
    echoed, stored = _approve_and_read_request_id(client, {})
    assert GENERATED.fullmatch(echoed)
    assert stored == echoed


@pytest.mark.parametrize(
    "supplied",
    ["a" * 65, "has space", "semi;colon", "under_score", "x/../y", '{"forged":true}', ""],
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


@pytest.mark.parametrize(
    "supplied", ["a" * 64, "A", "0-9", "abc\n", "abc\r\nX: y", "a\tb", "ünïcode", "１２３", None]
)
def test_resolve_request_id_pattern(supplied):
    resolved = resolve_request_id(supplied)
    if supplied in ("a" * 64, "A", "0-9"):
        assert resolved == supplied
    else:
        assert GENERATED.fullmatch(resolved)
