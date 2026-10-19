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


def test_fnd3_concurrent_writers_keep_one_unbroken_chain(app):
    """Writers in parallel threads each read the last hash inside a BEGIN IMMEDIATE transaction, so the chain
    never forks: every entry's prev_hash is the hash of the entry before it and verify() stays ok."""
    import threading

    from backend.platform import audit

    threads, per_thread, errors = 8, 25, []

    def worker(n: int) -> None:
        try:
            for i in range(per_thread):
                with app.state.db.session() as session:
                    audit.write(
                        session,
                        app="testapp",
                        actor_id=f"thread-{n}",
                        action="widget.touch",
                        record_id=f"TEST-WID-{n:02d}{i:04d}",
                    )
                    session.commit()
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    workers = [threading.Thread(target=worker, args=(n,)) for n in range(threads)]
    for t in workers:
        t.start()
    for t in workers:
        t.join()
    assert errors == []

    with app.state.db.session() as session:
        result = audit.verify(session)
        rows = session.execute(
            select(audit.AuditEntry.prev_hash, audit.AuditEntry.hash).order_by(audit.AuditEntry.id)
        ).all()
    assert result["ok"] is True
    assert len(rows) >= threads * per_thread
    assert len({h for _, h in rows}) == len(rows)
    for (_, prev_hash), (next_prev, _) in zip(rows, rows[1:], strict=False):
        assert next_prev == prev_hash


def _touch(app, n: int) -> None:
    with app.state.db.session() as session:
        for i in range(n):
            audit.write(session, app="testapp", actor_id="manager_1", action="widget.touch", record_id=str(i))
        session.commit()


def test_health_reads_without_waiting_for_the_write_lock(client, app):
    """/health is public, so it must never queue behind (or hold) the SQLite write lock."""
    import time

    _touch(app, 3)
    with app.state.db.engine.connect() as writer:
        writer.begin()  # BEGIN IMMEDIATE: another request holding the write lock mid-transaction
        started = time.perf_counter()
        health = client.get("/health").json()
        elapsed = time.perf_counter() - started
        writer.rollback()
    assert health["audit"] == {"entries": 3, "chain_ok": True}
    assert elapsed < 5


def test_read_sessions_cannot_write(app):
    with app.state.db.read_session() as session:
        with pytest.raises(DatabaseError, match="readonly"):
            session.execute(text("UPDATE test_widgets SET status = 'x'"))


def test_chain_status_is_cached_and_incremental(app):
    """Repeated /health calls only check entries appended since the last good one; a full re-walk runs at
    most once per interval, and /audit/verify (full) always walks everything and refreshes the cache."""
    now = [0.0]
    verifier = audit.ChainVerifier(full_interval=60, clock=lambda: now[0])
    _touch(app, 3)
    with app.state.db.read_session() as session:
        assert verifier.status(session)["entries"] == 3
    _touch(app, 2)
    with app.state.db.read_session() as session:
        assert verifier.status(session) == {"ok": True, "entries": 5, "first_bad_id": None, "reason": None}

    with app.state.db.engine.begin() as conn:
        conn.execute(text("DROP TRIGGER audit_entries_no_update"))
        conn.execute(text("UPDATE audit_entries SET actor_id = 'manager_2' WHERE id = 2"))
    with app.state.db.read_session() as session:
        assert (
            verifier.status(session)["ok"] is True
        )  # already-verified rows are re-checked on the next full walk
    now[0] = 61
    with app.state.db.read_session() as session:
        result = verifier.status(session)
    assert result["ok"] is False and result["first_bad_id"] == 2

    fresh = audit.ChainVerifier(full_interval=60, clock=lambda: 0.0)
    with app.state.db.read_session() as session:
        fresh.status(session)
        assert fresh.full(session)["first_bad_id"] == 2
        assert fresh.status(session)["ok"] is False


def test_chain_status_rewalks_after_the_database_is_reset(app):
    verifier = audit.ChainVerifier(full_interval=3600, clock=lambda: 0.0)
    _touch(app, 4)
    with app.state.db.read_session() as session:
        assert verifier.status(session)["entries"] == 4
    with app.state.db.engine.begin() as conn:
        conn.execute(text("DROP TRIGGER audit_entries_no_delete"))
        conn.execute(text("DELETE FROM audit_entries"))
    _touch(app, 1)
    with app.state.db.read_session() as session:
        assert verifier.status(session) == {"ok": True, "entries": 1, "first_bad_id": None, "reason": None}


def test_record_history_trims_oversight_entries_for_roles_without_audit_read(app):
    from backend.tests.testapp.app import POLICY

    manager = User(id="manager_1", name="M", roles={"testapp": RoleAssignment("testapp", "manager")})
    viewer = User(id="viewer_north", name="V", roles={"testapp": RoleAssignment("testapp", "viewer")})
    ref = "TEST-WID-000001"
    with app.state.db.session() as session:
        for action, diff in [
            ("widget.approve", {"status": {"from": "requested", "to": "approved"}}),
            ("security.denied", {"code": "SOD_VIOLATION"}),
            ("widget.read_unmasked", {"fields": ["owner_name"]}),
        ]:
            audit.write(
                session,
                app="testapp",
                actor_id="manager_1",
                action=action,
                record_type="widget",
                record_id=ref,
                diff=diff,
                request_id="req-1",
            )
        session.commit()
        kwargs = {"record_type": "widget", "record_id": ref, "workflow_actions": ("widget.approve",)}
        full = audit.record_history(session, POLICY, manager, **kwargs)
        trimmed = audit.record_history(session, POLICY, viewer, **kwargs)
    actions = [e["action"] for e in full["items"]]
    assert actions == ["widget.approve", "security.denied", "widget.read_unmasked"]
    assert full["items"][0]["request_id"] == "req-1" and full["items"][0]["hash"]
    assert trimmed["total"] == 1 and [e["action"] for e in trimmed["items"]] == ["widget.approve"]
    entry = trimmed["items"][0]
    assert not {"request_id", "hash", "prev_hash"} & entry.keys()
    assert entry["actor_id"] == "manager_1" and entry["diff"]["status"]["to"] == "approved"
