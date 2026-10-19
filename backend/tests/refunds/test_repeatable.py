"""REP-1 to REP-4: the Refunds Desk gets every control from the foundation and policy.yaml alone."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.tests.refunds.conftest import ELENA, GABRIELA, HUGO, INES, JAVIER, KARLA, as_user, build_app

SMALL_NE = 1  # $200 goodwill, requested by Gabriela
LARGE_NE = 2  # $7,500 dispute, requested by Gabriela
SMALL_MW = 3  # midwest, requested by Hugo
LARGE_BY_INES = 4  # $9,000, requested by an approver
APPROVED_SE = 5
PAID_W = 6


def get(client, refund_id, user):
    return client.get(f"/refunds/{refund_id}", headers=as_user(user)).json()


def post(client, refund_id, action, user, version=None):
    version = version if version is not None else get(client, refund_id, INES)["version"]
    return client.post(f"/refunds/{refund_id}/{action}", json={"version": version}, headers=as_user(user))


def history(client, refund_id, user=INES):
    return client.get(f"/refunds/{refund_id}/history", headers=as_user(user)).json()["items"]


NEW_REFUND = {
    "customer_name": "Gus Green",
    "card_last4": "4242",
    "amount_cents": 750_000,
    "type": "goodwill",
    "reason": "Duplicate charge.",
    "region": "northeast",
}


# ---- REP-1: sign-in, roles, scope, approvals and audit come from the foundation -------------------------


def test_rep1_sign_in_fails_closed(client, tmp_path):
    assert client.get("/refunds").status_code == 401
    assert client.get("/refunds", headers=as_user("TEST-USR-NOBODY")).status_code == 401
    r = client.get("/refunds", headers=as_user("TEST-USR-GHOST"))
    assert r.status_code == 403 and r.json()["code"] == "UNKNOWN_ROLE"
    with TestClient(build_app(tmp_path / "prod.db", env="prod")) as prod:
        assert prod.get("/refunds", headers=as_user(INES)).status_code == 401


def test_rep1_permissions_come_from_policy_yaml(client):
    for user, action in ((GABRIELA, "approve"), (KARLA, "approve"), (ELENA, "approve"), (GABRIELA, "reject")):
        r = post(client, SMALL_NE, action, user)
        assert r.status_code == 403 and r.json()["code"] == "FORBIDDEN", (user, action)
    for user in (GABRIELA, INES, ELENA):
        r = post(client, APPROVED_SE, "pay", user)
        assert r.status_code == 403 and r.json()["code"] == "FORBIDDEN", user
    for user in (KARLA, ELENA):
        r = client.post("/refunds", json=NEW_REFUND, headers=as_user(user))
        assert r.status_code == 403 and r.json()["code"] == "FORBIDDEN", user
    assert client.get("/audit?app=refunds", headers=as_user(GABRIELA)).status_code == 403
    assert client.get("/audit?app=refunds", headers=as_user(KARLA)).status_code == 403
    assert client.get("/audit?app=refunds", headers=as_user(ELENA)).status_code == 200
    assert client.get("/audit?app=refunds", headers=as_user(INES)).status_code == 200


def test_rep1_elena_holds_roles_in_both_apps(client):
    roles = {r["app"]: r["role"] for r in client.get("/me", headers=as_user(ELENA)).json()["roles"]}
    assert roles == {"kyc": "auditor", "refunds": "auditor"}
    assert client.get("/kyc/cases", headers=as_user(ELENA)).status_code == 200
    assert client.get("/refunds", headers=as_user(ELENA)).status_code == 200
    r = client.get("/refunds", headers=as_user(INES.replace("INES", "CAMILA")))
    assert r.status_code == 403 and r.json()["code"] == "NO_ROLE"


def test_rep1_agent_scope_in_list_count_lookup_and_request(client):
    page = client.get("/refunds", headers=as_user(GABRIELA)).json()
    assert page["total"] == 3 and {r["region"] for r in page["items"]} == {"northeast", "southeast"}
    assert client.get("/refunds/count", headers=as_user(GABRIELA)).json() == {"count": 3}
    assert client.get("/refunds?region=midwest", headers=as_user(GABRIELA)).json()["total"] == 0
    assert client.get(f"/refunds/{SMALL_MW}", headers=as_user(GABRIELA)).status_code == 404
    assert client.get(f"/refunds/{SMALL_MW}/history", headers=as_user(GABRIELA)).status_code == 404
    assert client.get(f"/refunds/{SMALL_NE}", headers=as_user(HUGO)).status_code == 404
    assert client.get("/refunds", headers=as_user(INES)).json()["total"] == 6
    r = client.post("/refunds", json={**NEW_REFUND, "region": "midwest"}, headers=as_user(GABRIELA))
    assert r.status_code == 403 and r.json()["code"] == "OUT_OF_SCOPE"
    assert (
        client.post("/refunds", json={**NEW_REFUND, "region": "midwest"}, headers=as_user(INES)).status_code
        == 201
    )


def test_rep1_every_state_change_is_audited_and_the_chain_verifies(client):
    r = client.post("/refunds", json={**NEW_REFUND, "amount_cents": 1_000}, headers=as_user(GABRIELA))
    assert r.status_code == 201
    rid, ref = r.json()["id"], r.json()["reference"]
    assert ref == "TEST-RFD-000007"
    assert post(client, rid, "approve", INES).json()["status"] == "approved"
    assert post(client, rid, "pay", KARLA).json()["status"] == "paid"
    actions = sorted(e["action"] for e in history(client, rid))
    assert actions == ["refund.approve", "refund.pay", "refund.request"]
    assert all(e["actor_id"] for e in history(client, rid))
    verify = client.get("/audit/verify?app=refunds", headers=as_user(ELENA)).json()
    assert verify["ok"] is True and verify["entries"] >= 3


# ---- REP-2: the requester cannot approve their own refund -------------------------------------------------


def test_rep2_requester_cannot_approve_own_refund(client):
    before = get(client, LARGE_BY_INES, INES)
    r = post(client, LARGE_BY_INES, "approve", INES)
    assert r.status_code == 403 and r.json()["code"] == "SOD_VIOLATION"
    after = get(client, LARGE_BY_INES, INES)
    assert (
        after["status"] == "requested" and after["version"] == before["version"] and after["approvals"] == []
    )
    denied = [e for e in history(client, LARGE_BY_INES) if e["action"] == "security.denied"]
    assert denied and denied[0]["diff"]["code"] == "SOD_VIOLATION" and denied[0]["actor_id"] == INES
    r = post(client, LARGE_BY_INES, "approve", JAVIER)
    assert r.status_code == 200 and r.json()["status"] == "pending_second_approval"


def test_rep2_agent_requester_gets_forbidden_not_sod(client):
    """An agent has no approve permission at all: FORBIDDEN, not SOD_VIOLATION, so the two differ."""
    r = post(client, SMALL_NE, "approve", GABRIELA)
    assert r.status_code == 403 and r.json()["code"] == "FORBIDDEN"


# ---- REP-3: two approvals from two different approvers above $5,000 -------------------------------------


def test_rep3_large_refund_needs_two_distinct_approvers(client):
    assert get(client, LARGE_NE, INES)["approvals_required"] == 2
    first = post(client, LARGE_NE, "approve", INES)
    assert first.status_code == 200
    assert first.json()["status"] == "pending_second_approval" and first.json()["approved_at"] is None
    assert [a["approver_id"] for a in first.json()["approvals"]] == [INES]
    again = post(client, LARGE_NE, "approve", INES)
    assert again.status_code == 403 and again.json()["code"] == "SOD_VIOLATION"
    assert get(client, LARGE_NE, INES)["status"] == "pending_second_approval"
    assert post(client, LARGE_NE, "pay", KARLA).status_code == 409
    second = post(client, LARGE_NE, "approve", JAVIER)
    assert second.status_code == 200 and second.json()["status"] == "approved"
    assert [a["approver_id"] for a in second.json()["approvals"]] == [INES, JAVIER]
    paid = post(client, LARGE_NE, "pay", KARLA)
    assert paid.status_code == 200 and paid.json()["status"] == "paid" and paid.json()["paid_at"]
    approvals = [e["diff"]["approvals"] for e in history(client, LARGE_NE) if e["action"] == "refund.approve"]
    assert sorted(approvals) == ["1 of 2", "2 of 2"]


def test_rep3_small_refund_needs_one_approval(client):
    assert get(client, SMALL_NE, INES)["approvals_required"] == 1
    r = post(client, SMALL_NE, "approve", JAVIER)
    assert r.status_code == 200 and r.json()["status"] == "approved" and r.json()["approved_at"]


def test_rep3_threshold_is_strictly_above_5000(client):
    r = client.post("/refunds", json={**NEW_REFUND, "amount_cents": 500_000}, headers=as_user(GABRIELA))
    assert r.json()["approvals_required"] == 1
    r = client.post("/refunds", json={**NEW_REFUND, "amount_cents": 500_001}, headers=as_user(GABRIELA))
    assert r.json()["approvals_required"] == 2


def test_workflow_reject_version_and_transitions(client):
    r = post(client, SMALL_NE, "reject", INES)
    assert r.status_code == 200 and r.json()["status"] == "rejected" and r.json()["rejecter_id"] == INES
    assert post(client, SMALL_NE, "approve", JAVIER).status_code == 409
    assert post(client, LARGE_NE, "approve", INES).json()["status"] == "pending_second_approval"
    r = post(client, LARGE_NE, "reject", JAVIER)
    assert r.status_code == 200 and r.json()["status"] == "rejected"
    stale = post(client, SMALL_MW, "approve", INES, version=99)
    assert stale.status_code == 409 and stale.json()["code"] == "VERSION_CONFLICT"
    assert post(client, SMALL_MW, "pay", KARLA).status_code == 409
    assert post(client, PAID_W, "approve", INES).status_code == 409
    assert post(client, PAID_W, "pay", KARLA).status_code == 409
    r = client.post(
        "/refunds", json={**NEW_REFUND, "type": "dispute", "reported_on": None}, headers=as_user(GABRIELA)
    )
    assert r.status_code == 400 and r.json()["code"] == "REPORTED_ON_REQUIRED"


# ---- REP-4: last 4 digits only, customer names masked for agents ------------------------------------------


def test_rep4_only_last4_is_accepted_and_stored(client, db_path):
    import sqlite3

    for bad in ("4242424242424242", "424", "42a2", ""):
        r = client.post("/refunds", json={**NEW_REFUND, "card_last4": bad}, headers=as_user(GABRIELA))
        assert r.status_code == 422, bad
    r = client.post("/refunds", json=NEW_REFUND, headers=as_user(GABRIELA))
    assert r.status_code == 201 and r.json()["card_last4"] == "4242"
    stored = sqlite3.connect(db_path).execute(
        "select card_last4 from refunds where id = ?", (r.json()["id"],)
    )
    assert stored.fetchone() == ("4242",)
    entry = next(e for e in history(client, r.json()["id"]) if e["action"] == "refund.request")
    assert entry["diff"]["customer_name"] == {"changed": True} and entry["diff"]["card_last4"] == {
        "changed": True
    }
    assert "Gus Green" not in str(entry) and "4242" not in str(entry["diff"])


def test_rep4_customer_name_masked_for_agents_and_auditors(client):
    rows = client.get("/refunds?q=TEST-RFD-000001", headers=as_user(GABRIELA)).json()["items"]
    assert rows[0]["customer_name"] == "A. R." and rows[0]["masked"] is True
    assert get(client, SMALL_NE, GABRIELA)["customer_name"] == "A. R."
    assert get(client, SMALL_NE, ELENA)["customer_name"] == "A. R."
    assert (
        get(client, SMALL_NE, INES)["customer_name"] == "Ana Ruiz"
        and get(client, SMALL_NE, INES)["masked"] is False
    )
    assert get(client, SMALL_NE, KARLA)["customer_name"] == "Ana Ruiz"
    body = client.get("/refunds?page_size=200", headers=as_user(GABRIELA)).text
    for secret in ("Ana Ruiz", "Bo Chen", "Ed Fox"):
        assert secret not in body


def test_seed_queue_total_filters_and_paging(big_client):
    page = big_client.get("/refunds?page_size=50", headers=as_user(INES)).json()
    assert page["total"] == 20_000 and len(page["items"]) == 50
    open_page = big_client.get(
        "/refunds?status=requested,pending_second_approval&sort=created_at&order=asc", headers=as_user(INES)
    ).json()
    assert 0 < open_page["total"] < 20_000
    assert open_page["items"][0]["created_at"] <= open_page["items"][-1]["created_at"]
    by_region = sum(
        big_client.get(f"/refunds/count?region={r}", headers=as_user(INES)).json()["count"]
        for r in ("northeast", "southeast", "midwest", "west")
    )
    assert by_region == 20_000
    ne_se = big_client.get("/refunds", headers=as_user(GABRIELA)).json()["total"]
    assert ne_se == sum(
        big_client.get(f"/refunds/count?region={r}", headers=as_user(INES)).json()["count"]
        for r in ("northeast", "southeast")
    )
    disputes = big_client.get("/refunds/count?type=dispute", headers=as_user(INES)).json()["count"]
    assert 5_000 < disputes < 9_000
    search = big_client.get("/refunds?q=1234", headers=as_user(INES)).json()
    assert search["total"] == 1 and search["items"][0]["reference"] == "TEST-RFD-001234"
    verify = big_client.get("/audit/verify?app=refunds", headers=as_user(ELENA)).json()
    assert verify["ok"] is True


def test_agent_history_shows_only_workflow_steps(client):
    assert post(client, LARGE_NE, "approve", INES).status_code == 200
    assert post(client, LARGE_NE, "approve", INES).json()["code"] == "SOD_VIOLATION"
    full = history(client, LARGE_NE, ELENA)
    assert {"security.denied", "refund.approve"} <= {e["action"] for e in full}
    assert all(e["hash"] and "request_id" in e for e in full)
    trimmed = client.get(f"/refunds/{LARGE_NE}/history", headers=as_user(GABRIELA)).json()
    assert trimmed["total"] == len(trimmed["items"])
    assert {e["action"] for e in trimmed["items"]} == {"refund.approve"}
    assert not any({"request_id", "hash", "prev_hash"} & e.keys() for e in trimmed["items"])
