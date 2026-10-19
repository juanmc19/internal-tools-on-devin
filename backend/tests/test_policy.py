"""FND-2: roles, permissions, row scope, masked fields and approval rules come from policy.yaml alone."""

import pytest

from backend.platform.policy import Policy, PolicyError
from backend.tests.conftest import as_user
from backend.tests.testapp.app import POLICY

BASE = {
    "app": "x",
    "permissions": ["thing.read"],
    "roles": {"r": {"permissions": ["thing.read"], "scope": "all"}},
}


def test_fnd2_policy_loads_roles_permissions_scope_masking_and_approvals_from_yaml():
    assert POLICY.permissions >= {"widget.read", "widget.approve", "audit.read"}
    assert POLICY.roles["viewer"].scope_field == "region"
    assert POLICY.roles["viewer"].scope_attribute == "regions"
    assert POLICY.roles["manager"].scope_field is None
    assert POLICY.profiles["standard"]["owner_name"] == "initials"
    rule = POLICY.approval("approve")
    assert rule.distinct_from == ("requested_by", "approvals.approver_id")
    assert rule.default_count == 1 and rule.count_rules[0].gt == 1000 and rule.count_rules[0].count == 2


def test_fnd2_policy_fails_closed_at_load_time():
    with pytest.raises(PolicyError, match="undeclared permissions"):
        Policy.from_dict({**BASE, "roles": {"r": {"permissions": ["thing.delete"], "scope": "all"}}})
    with pytest.raises(PolicyError, match="must declare a scope"):
        Policy.from_dict({**BASE, "roles": {"r": {"permissions": ["thing.read"]}}})
    with pytest.raises(PolicyError, match="unknown masking profile"):
        Policy.from_dict({**BASE, "roles": {"r": {"permissions": [], "scope": "all", "masking": "nope"}}})
    with pytest.raises(PolicyError, match="unknown strategy"):
        Policy.from_dict({**BASE, "masking": {"profiles": {"p": {"f": "rot13"}}}})


def test_fnd2_unknown_permission_fails_closed_at_request_time(client):
    from backend.platform.auth import RoleAssignment, User
    from backend.platform.errors import ApiError
    from backend.tests.conftest import USERS  # noqa: F401

    manager = User(id="manager_1", name="M", roles={"testapp": RoleAssignment("testapp", "manager")})
    with pytest.raises(ApiError) as excinfo:
        POLICY.require(manager, "widget.delete")
    assert excinfo.value.status == 403 and excinfo.value.code == "UNKNOWN_PERMISSION"
    nobody = User(id="n", name="N", roles={})
    with pytest.raises(ApiError) as excinfo:
        POLICY.require(nobody, "widget.read")
    assert excinfo.value.code == "NO_ROLE"


def test_fnd2_permission_denied_is_403_and_recorded(client):
    response = client.post("/testapp/widgets/1/approve", headers=as_user("viewer_north"))
    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"
    entries = client.get("/audit?app=testapp&action=security.denied", headers=as_user("manager_1")).json()
    assert entries["total"] == 1
    assert entries["items"][0]["diff"] == {"code": "FORBIDDEN"}
    assert entries["items"][0]["actor_id"] == "viewer_north"


def test_fnd2_row_scope_applies_to_lists_counts_and_lookups(client):
    page = client.get("/testapp/widgets", headers=as_user("viewer_north")).json()
    assert page["total"] == 3
    assert {w["region"] for w in page["items"]} == {"north"}
    assert client.get("/testapp/widgets/count", headers=as_user("viewer_north")).json()["count"] == 3
    # an out-of-scope row is a 404, not a 403, so its existence is not revealed
    assert client.get("/testapp/widgets/3", headers=as_user("viewer_north")).status_code == 404
    assert client.get("/testapp/widgets/1", headers=as_user("viewer_north")).status_code == 200
    # a filter cannot widen the scope
    page = client.get("/testapp/widgets?region=south", headers=as_user("viewer_north")).json()
    assert page["total"] == 0
    # empty scope attribute sees nothing
    assert client.get("/testapp/widgets", headers=as_user("viewer_none")).json()["total"] == 0
    # unscoped role sees everything
    assert client.get("/testapp/widgets", headers=as_user("manager_1")).json()["total"] == 5


def test_fnd2_masking_by_role_in_every_response(client):
    masked = client.get("/testapp/widgets/1", headers=as_user("viewer_north")).json()
    assert masked["owner_name"] == "A. R."
    assert masked["id_number"] == "\u2022\u2022\u2022\u20224567"
    assert masked["address"] == "Austin"
    assert masked["born_on"] == "\u2022\u2022\u2022\u2022-\u2022\u2022-12"
    listed = client.get("/testapp/widgets", headers=as_user("viewer_north")).json()["items"][0]
    assert listed["owner_name"] == "A. R."
    clear = client.get("/testapp/widgets/1", headers=as_user("manager_1")).json()
    assert clear["owner_name"] == "Ana Ruiz" and clear["address"] == "12 Elm Street, Austin"
    refused = client.get("/testapp/widgets/1?unmasked=true", headers=as_user("viewer_north"))
    assert refused.status_code == 403 and refused.json()["code"] == "PII_MASKED_FOR_ROLE"


def test_fnd2_separation_of_duties_requester_cannot_approve(client):
    # widget 3 was requested by manager_1, who also holds widget.approve
    refused = client.post("/testapp/widgets/3/approve", headers=as_user("manager_1"))
    assert refused.status_code == 403
    assert refused.json()["code"] == "SOD_VIOLATION"
    unchanged = client.get("/testapp/widgets/3", headers=as_user("manager_1")).json()
    assert unchanged["status"] == "requested" and unchanged["approvals"] == []
    denied = client.get(
        "/audit?app=testapp&action=security.denied&record_id=TEST-WID-000003", headers=as_user("manager_1")
    ).json()
    assert denied["total"] == 1 and denied["items"][0]["diff"] == {"code": "SOD_VIOLATION"}
    ok = client.post("/testapp/widgets/3/approve", headers=as_user("manager_2"))
    assert ok.status_code == 200 and ok.json()["status"] == "approved"


def test_fnd2_two_distinct_approvals_above_threshold(client):
    # widget 2 is 2,500 > 1,000, so it needs two approvals from two different managers
    first = client.post("/testapp/widgets/2/approve", headers=as_user("manager_1")).json()
    assert first["status"] == "pending" and first["approvals"] == ["manager_1"]
    again = client.post("/testapp/widgets/2/approve", headers=as_user("manager_1"))
    assert again.status_code == 403 and again.json()["code"] == "SOD_VIOLATION"
    second = client.post("/testapp/widgets/2/approve", headers=as_user("manager_2")).json()
    assert second["status"] == "approved" and second["approvals"] == ["manager_1", "manager_2"]
    # widget 1 is 500, one approval is enough
    one = client.post("/testapp/widgets/1/approve", headers=as_user("manager_1")).json()
    assert one["status"] == "approved"
