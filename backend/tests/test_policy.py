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


def _denied(client, **filters) -> list[dict]:
    query = "&".join(f"{k}={v}" for k, v in filters.items())
    url = f"/audit?app=testapp&action=security.denied&page_size=100&{query}"
    return client.get(url, headers=as_user("manager_1")).json()["items"]


def test_repeated_identical_refusals_are_coalesced(client, app):
    """The same 403 hammered in a loop writes one entry per window; the next one carries the repeat count."""
    now = [0.0]
    app.state.refusals._clock = lambda: now[0]
    for _ in range(20):
        assert client.get("/audit?app=testapp", headers=as_user("viewer_north")).status_code == 403
    entries = _denied(client, actor_id="viewer_north")
    assert len(entries) == 1 and entries[0]["diff"] == {"code": "FORBIDDEN"}
    now[0] = 61
    client.get("/audit?app=testapp", headers=as_user("viewer_north"))
    entries = _denied(client, actor_id="viewer_north")
    assert len(entries) == 2 and entries[0]["diff"] == {"code": "FORBIDDEN", "repeats": 19}


def test_distinct_refusals_are_each_recorded_up_to_a_per_actor_budget(app):
    from backend.platform import audit

    gate = audit.RefusalGate(window=60, per_actor=3, clock=lambda: 0.0)
    admitted = [gate.admit(("testapp", "u1", "FORBIDDEN", "widget", str(i)), "u1") for i in range(5)]
    assert admitted == [0, 0, 0, None, None]
    assert gate.admit(("testapp", "u2", "FORBIDDEN", "widget", "0"), "u2") == 0


def test_refusal_write_runs_off_the_event_loop(client, app, monkeypatch):
    import asyncio

    from backend.platform import audit

    seen = []

    def fake(*_args, **_kwargs):
        try:
            asyncio.get_running_loop()
            seen.append("event loop")
        except RuntimeError:
            seen.append("worker thread")

    monkeypatch.setattr(audit, "record_refusal", fake)
    assert client.get("/audit?app=testapp", headers=as_user("viewer_north")).status_code == 403
    assert seen == ["worker thread"]


APPROVALS_BASE = {**BASE, "approvals": {"approve": {"distinct_from": ["requested_by"]}}}


def _manifest(policy: Policy, model: type | None):
    from dataclasses import replace

    from backend.tests.testapp.app import MANIFEST

    return replace(MANIFEST, key=policy.app, policy=policy, record_model=model)


def test_fnd2_mistyped_approval_field_fails_closed_at_registration():
    from backend.platform.registry import Registry
    from backend.tests.testapp.app import Widget

    typo = Policy.from_dict({**BASE, "approvals": {"approve": {"distinct_from": ["requestd_by"]}}})
    with pytest.raises(PolicyError, match="'requestd_by' is not a field on Widget"):
        Registry([_manifest(typo, Widget)])
    bad_hop = Policy.from_dict(
        {**BASE, "approvals": {"approve": {"distinct_from": ["approvals.aprover_id"]}}}
    )
    with pytest.raises(PolicyError, match="'approvals.aprover_id' is not a field"):
        Registry([_manifest(bad_hop, Widget)])
    count_typo = Policy.from_dict(
        {
            **BASE,
            "approvals": {
                "approve": {"count": {"rules": [{"when": {"field": "amout", "gt": 1}, "then": 2}]}}
            },
        }
    )
    with pytest.raises(PolicyError, match="'amout' is not a field"):
        Registry([_manifest(count_typo, Widget)])
    with pytest.raises(PolicyError, match="needs record_model"):
        Registry([_manifest(Policy.from_dict(APPROVALS_BASE), None)])
    Registry([_manifest(Policy.from_dict(APPROVALS_BASE), Widget)])
    Registry([_manifest(POLICY, Widget)])


def test_fnd2_mistyped_approval_field_fails_closed_at_request_time():
    typo = Policy.from_dict({**BASE, "approvals": {"approve": {"distinct_from": ["requestd_by"]}}})
    with pytest.raises(PolicyError, match="requestd_by"):
        typo.check_separation("approve", "u1", {"requested_by": "u1"}, record_type="x", record_id="1")
    count_typo = Policy.from_dict(
        {
            **BASE,
            "approvals": {
                "approve": {"count": {"rules": [{"when": {"field": "amout", "gt": 1}, "then": 2}]}}
            },
        }
    )
    with pytest.raises(PolicyError, match="amout"):
        count_typo.required_approvals("approve", {"amount": 5})


def test_fnd2_overlapping_count_rules_require_the_strictest_match():
    tiers = [
        {"when": {"field": "amount", "gt": 1000}, "then": 2},
        {"when": {"field": "amount", "gt": 10000}, "then": 3},
    ]
    for rules in (tiers, list(reversed(tiers))):
        policy = Policy.from_dict(
            {**BASE, "approvals": {"approve": {"count": {"default": 1, "rules": rules}}}}
        )
        assert policy.required_approvals("approve", {"amount": 500}) == 1
        assert policy.required_approvals("approve", {"amount": 5000}) == 2
        assert policy.required_approvals("approve", {"amount": 60000}) == 3
        assert not policy.approvals_complete("approve", {"amount": 60000}, ["a", "b"])
        assert policy.approvals_complete("approve", {"amount": 60000}, ["a", "b", "c"])


def test_fnd2_app_policies_pass_field_checks():
    from backend.apps import MANIFESTS
    from backend.platform.registry import Registry

    Registry(MANIFESTS)
    assert all(m.record_model is not None for m in MANIFESTS if m.policy.approvals)
