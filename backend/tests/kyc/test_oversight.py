"""OVR-1, OVR-2, OVR-3 plus the claim → recommend → decide workflow rules."""

from __future__ import annotations

import pytest

from backend.apps.kyc import service
from backend.platform import audit
from backend.platform.auth import current_user  # noqa: F401  (documents the dependency chain)
from backend.tests.kyc.conftest import ANA, BRUNO, CAMILA, DIEGO, ELENA, as_user

NEW_MX = 1
RECOMMENDED_BY_CAMILA = 2
IN_REVIEW_BY_BRUNO = 5


def get(client, case_id, user):
    return client.get(f"/kyc/cases/{case_id}", headers=as_user(user)).json()


def history(client, case_id, user=CAMILA):
    return client.get(f"/kyc/cases/{case_id}/history", headers=as_user(user)).json()["items"]


def test_workflow_claim_recommend_decide(client):
    case = get(client, NEW_MX, ANA)
    r = client.post(f"/kyc/cases/{NEW_MX}/claim", json={"version": case["version"]}, headers=as_user(ANA))
    assert r.status_code == 200 and r.json()["status"] == "in_review" and r.json()["assignee_id"] == ANA
    r = client.post(
        f"/kyc/cases/{NEW_MX}/recommend",
        json={"version": r.json()["version"], "outcome": "approve", "note": "Documents check out."},
        headers=as_user(ANA),
    )
    assert r.status_code == 200 and r.json()["status"] == "recommended" and r.json()["recommender_id"] == ANA
    r = client.post(
        f"/kyc/cases/{NEW_MX}/decide",
        json={"version": r.json()["version"], "outcome": "approve"},
        headers=as_user(DIEGO),
    )
    assert r.status_code == 200 and r.json()["status"] == "approved" and r.json()["decider_id"] == DIEGO
    actions = [e["action"] for e in history(client, NEW_MX)]
    assert actions == ["case.decide", "case.recommend", "case.claim"] or sorted(actions) == sorted(
        ["case.claim", "case.recommend", "case.decide"]
    )
    note_entry = next(e for e in history(client, NEW_MX) if e["action"] == "case.recommend")
    assert note_entry["diff"]["recommendation_note"] == {"changed": True}
    assert "Documents check out." not in str(note_entry)


def test_ovr1_recommender_cannot_decide(client):
    before = get(client, RECOMMENDED_BY_CAMILA, CAMILA)
    r = client.post(
        f"/kyc/cases/{RECOMMENDED_BY_CAMILA}/decide",
        json={"version": before["version"], "outcome": "approve"},
        headers=as_user(CAMILA),
    )
    assert r.status_code == 403
    assert r.json()["code"] == "SOD_VIOLATION"
    after = get(client, RECOMMENDED_BY_CAMILA, CAMILA)
    assert after["status"] == "recommended" and after["version"] == before["version"]
    assert after["decider_id"] is None and after["decision"] is None
    denied = [e for e in history(client, RECOMMENDED_BY_CAMILA) if e["action"] == "security.denied"]
    assert denied and denied[0]["diff"]["code"] == "SOD_VIOLATION" and denied[0]["actor_id"] == CAMILA
    r = client.post(
        f"/kyc/cases/{RECOMMENDED_BY_CAMILA}/decide",
        json={"version": before["version"], "outcome": "reject"},
        headers=as_user(DIEGO),
    )
    assert r.status_code == 200 and r.json()["status"] == "rejected"


def test_permissions_by_role(client):
    r = client.post(
        f"/kyc/cases/{RECOMMENDED_BY_CAMILA}/decide",
        json={"version": 3, "outcome": "approve"},
        headers=as_user(ANA),
    )
    assert r.status_code == 403 and r.json()["code"] == "FORBIDDEN"
    r = client.post(f"/kyc/cases/{NEW_MX}/claim", json={"version": 1}, headers=as_user(ELENA))
    assert r.status_code == 403 and r.json()["code"] == "FORBIDDEN"
    assert client.get("/audit?app=kyc", headers=as_user(ANA)).status_code == 403
    assert client.get("/audit?app=kyc", headers=as_user(ELENA)).status_code == 200
    assert client.get("/audit/verify?app=kyc", headers=as_user(ELENA)).json()["ok"] is True


def test_transition_assignee_and_version_rules(client):
    r = client.post(f"/kyc/cases/{IN_REVIEW_BY_BRUNO}/claim", json={"version": 2}, headers=as_user(BRUNO))
    assert r.status_code == 409 and r.json()["code"] == "INVALID_TRANSITION"
    r = client.post(
        f"/kyc/cases/{IN_REVIEW_BY_BRUNO}/recommend",
        json={"version": 2, "outcome": "approve", "note": "x"},
        headers=as_user(CAMILA),
    )
    assert r.status_code == 403 and r.json()["code"] == "NOT_ASSIGNEE"
    r = client.post(
        f"/kyc/cases/{IN_REVIEW_BY_BRUNO}/recommend",
        json={"version": 2, "outcome": "approve", "note": "   "},
        headers=as_user(BRUNO),
    )
    assert r.status_code == 400 and r.json()["code"] == "NOTE_REQUIRED"
    r = client.post(
        f"/kyc/cases/{IN_REVIEW_BY_BRUNO}/recommend",
        json={"version": 1, "outcome": "approve", "note": "stale"},
        headers=as_user(BRUNO),
    )
    assert r.status_code == 409 and r.json()["code"] == "VERSION_CONFLICT"
    r = client.post(
        f"/kyc/cases/{IN_REVIEW_BY_BRUNO}/recommend",
        json={"version": 2, "outcome": "maybe", "note": "ok"},
        headers=as_user(BRUNO),
    )
    assert r.status_code == 400 and r.json()["code"] == "INVALID_OUTCOME"
    assert get(client, IN_REVIEW_BY_BRUNO, BRUNO)["status"] == "in_review"
    assert [e for e in history(client, IN_REVIEW_BY_BRUNO) if e["action"].startswith("case.")] == []


def test_ovr2_audit_entry_commits_with_the_change_or_not_at_all(app):
    from backend.apps.kyc.models import Case
    from backend.platform.auth import RoleAssignment, User

    ana = User(
        id=ANA,
        name="Ana Ruiz",
        roles={"kyc": RoleAssignment(app="kyc", role="analyst", attributes={"countries": ["MX", "CO"]})},
    )
    session = app.state.db.session()

    def boom():
        raise RuntimeError("commit failed")

    session.commit = boom  # type: ignore[method-assign]
    with pytest.raises(RuntimeError):
        service.claim(session, ana, NEW_MX, version=1)
    session.rollback()
    session.close()

    with app.state.db.session() as check:
        case = check.get(Case, NEW_MX)
        assert case.status == "new" and case.version == 1 and case.assignee_id is None
        assert check.scalars(audit.entries_for_record("kyc", "case", "TEST-KYC-000001")).all() == []

    with app.state.db.session() as session:
        service.claim(session, ana, NEW_MX, version=1)
    with app.state.db.session() as check:
        assert check.get(Case, NEW_MX).status == "in_review"
        entries = check.scalars(audit.entries_for_record("kyc", "case", "TEST-KYC-000001")).all()
        assert [e.action for e in entries] == ["case.claim"]
        assert audit.verify(check)["ok"] is True


def test_ovr3_chain_verifies_triggers_block_edits_and_tampering_is_named(client, raw):
    test_ovr1_recommender_cannot_decide(client)
    verify = client.get("/audit/verify?app=kyc", headers=as_user(CAMILA)).json()
    assert verify["ok"] is True and verify["entries"] >= 3
    entries = raw.execute("SELECT id, prev_hash, hash FROM audit_entries ORDER BY id").fetchall()
    for (_, prev, _), (_, _, prev_hash_expected) in zip(entries[1:], entries[:-1], strict=False):
        assert prev == prev_hash_expected

    import sqlite3

    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        raw.execute("UPDATE audit_entries SET action = 'case.claim' WHERE id = 1")
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        raw.execute("DELETE FROM audit_entries WHERE id = 1")

    target = entries[1][0]
    raw.execute("DROP TRIGGER audit_entries_no_update")
    raw.execute("UPDATE audit_entries SET actor_id = 'TEST-USR-MALLORY' WHERE id = ?", (target,))
    raw.commit()
    verify = client.get("/audit/verify?app=kyc", headers=as_user(ELENA)).json()
    assert verify["ok"] is False and verify["first_bad_id"] == target and verify["reason"]
