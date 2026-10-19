"""Audit log: same-transaction writes, hash chain, append-only triggers, verify endpoint (OVR-2, OVR-3)."""

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DatabaseError

from backend.platform import audit
from backend.platform.auth import RoleAssignment, User
from backend.tests.conftest import as_user
from backend.tests.testapp.app import Widget, rename_then_fail


def test_ovr2_state_change_and_audit_entry_share_a_transaction(client, app):
    client.post("/testapp/widgets/1/approve", headers=as_user("manager_1"))
    entries = client.get("/audit?app=testapp&record_id=TEST-WID-000001", headers=as_user("manager_1")).json()
    assert entries["total"] == 1
    entry = entries["items"][0]
    assert entry["action"] == "widget.approve"
    assert entry["diff"]["status"] == {"from": "requested", "to": "approved"}
    assert entry["request_id"]


def test_ovr2_failed_change_writes_no_audit_entry(app):
    manager = User(id="manager_1", name="M", roles={"testapp": RoleAssignment("testapp", "manager")})
    with app.state.db.session() as session:
        with pytest.raises(RuntimeError):
            rename_then_fail(session, manager, 1)
        session.rollback()
    with app.state.db.session() as session:
        assert session.scalar(select(Widget.status).where(Widget.id == 1)) == "requested"
        assert (
            session.scalar(select(audit.AuditEntry.id).where(audit.AuditEntry.action == "widget.break"))
            is None
        )


def test_ovr3_entries_are_hash_chained(client, app):
    client.post("/testapp/widgets/1/approve", headers=as_user("manager_1"))
    client.post("/testapp/widgets/2/approve", headers=as_user("manager_1"))
    client.post("/testapp/widgets/2/approve", headers=as_user("manager_2"))
    with app.state.db.session() as session:
        rows = session.scalars(select(audit.AuditEntry).order_by(audit.AuditEntry.id)).all()
    assert len(rows) == 3
    assert rows[0].prev_hash == audit.GENESIS
    assert rows[1].prev_hash == rows[0].hash and rows[2].prev_hash == rows[1].hash
    assert len(rows[0].hash) == 64
    result = client.get("/audit/verify?app=testapp", headers=as_user("manager_1")).json()
    assert result == {"ok": True, "entries": 3, "first_bad_id": None, "reason": None}


def test_ovr3_triggers_block_update_and_delete(client, app):
    client.post("/testapp/widgets/1/approve", headers=as_user("manager_1"))
    with app.state.db.engine.begin() as conn:
        with pytest.raises(DatabaseError, match="append-only"):
            conn.execute(text("UPDATE audit_entries SET action = 'x' WHERE id = 1"))
    with app.state.db.engine.begin() as conn:
        with pytest.raises(DatabaseError, match="append-only"):
            conn.execute(text("DELETE FROM audit_entries WHERE id = 1"))
    with app.state.db.session() as session:
        assert (
            session.scalar(select(audit.AuditEntry.action).where(audit.AuditEntry.id == 1))
            == "widget.approve"
        )


def test_ovr3_verify_names_first_edited_row_on_tampered_copy(client, app):
    client.post("/testapp/widgets/1/approve", headers=as_user("manager_1"))
    client.post("/testapp/widgets/2/approve", headers=as_user("manager_1"))
    client.post("/testapp/widgets/2/approve", headers=as_user("manager_2"))
    # simulate an attacker with raw database access who drops the trigger and edits history
    with app.state.db.engine.begin() as conn:
        conn.execute(text("DROP TRIGGER audit_entries_no_update"))
        conn.execute(text("UPDATE audit_entries SET actor_id = 'manager_2' WHERE id = 2"))
    result = client.get("/audit/verify?app=testapp", headers=as_user("manager_1")).json()
    assert result["ok"] is False
    assert result["first_bad_id"] == 2
    assert result["reason"] == "hash mismatch"
    health = client.get("/health").json()
    assert health["audit"]["chain_ok"] is False


def test_audit_read_requires_permission_and_filters(client):
    client.post("/testapp/widgets/1/approve", headers=as_user("manager_1"))
    refused = client.get("/audit?app=testapp", headers=as_user("viewer_north"))
    assert refused.status_code == 403 and refused.json()["code"] == "FORBIDDEN"
    assert client.get("/audit?app=nope", headers=as_user("manager_1")).status_code == 404
    by_actor = client.get("/audit?app=testapp&actor_id=manager_1", headers=as_user("manager_1")).json()
    assert by_actor["total"] == 1
    page = client.get("/audit?app=testapp&page_size=1", headers=as_user("manager_1")).json()
    # newest first by default; the viewer's refusal above is the latest entry
    assert page["items"][0]["action"] == "security.denied" and page["total"] == 2


def test_audit_entries_hold_no_personal_data(client, app):
    client.post("/testapp/widgets/1/approve", headers=as_user("manager_1"))
    with app.state.db.session() as session:
        rows = session.scalars(select(audit.AuditEntry)).all()
    blob = " ".join(f"{r.diff} {r.record_id} {r.actor_id}" for r in rows)
    for pii in ["Ana Ruiz", "AB1234567", "Elm Street", "1987-04-12"]:
        assert pii not in blob
