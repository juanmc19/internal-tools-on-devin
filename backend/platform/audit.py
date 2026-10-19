"""Append-only, hash-chained audit log.

Entries are written in the caller's transaction (`write`) so a failed change leaves no entry, except
refusals (`record_refusal`) which get their own transaction because the refused change never commits.
SQLite triggers block UPDATE and DELETE; `verify` recomputes the chain and names the first bad row.
No personal data goes in here: ids, actions and diffs with masked fields reduced to {"changed": true}.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Index, Select, String, Text, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Mapped, Session, mapped_column

from backend.platform.db import Base

if TYPE_CHECKING:
    from backend.platform.db import Database

GENESIS = "0" * 64


class AuditEntry(Base):
    __tablename__ = "audit_entries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts: Mapped[str] = mapped_column(String(32))
    app: Mapped[str | None] = mapped_column(String(32), index=True)
    actor_id: Mapped[str | None] = mapped_column(String(64), index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    record_type: Mapped[str | None] = mapped_column(String(64))
    record_id: Mapped[str | None] = mapped_column(String(64))
    request_id: Mapped[str | None] = mapped_column(String(64))
    diff: Mapped[str] = mapped_column(Text, default="{}")
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))

    __table_args__ = (Index("ix_audit_record", "app", "record_type", "record_id"),)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "ts": self.ts,
            "app": self.app,
            "actor_id": self.actor_id,
            "action": self.action,
            "record_type": self.record_type,
            "record_id": self.record_id,
            "request_id": self.request_id,
            "diff": json.loads(self.diff or "{}"),
            "prev_hash": self.prev_hash,
            "hash": self.hash,
        }


TRIGGERS = {
    "audit_entries_no_update": (
        "CREATE TRIGGER IF NOT EXISTS audit_entries_no_update BEFORE UPDATE ON audit_entries "
        "BEGIN SELECT RAISE(ABORT, 'audit_entries is append-only'); END"
    ),
    "audit_entries_no_delete": (
        "CREATE TRIGGER IF NOT EXISTS audit_entries_no_delete BEFORE DELETE ON audit_entries "
        "BEGIN SELECT RAISE(ABORT, 'audit_entries is append-only'); END"
    ),
}


def install_audit_triggers(engine: Engine) -> None:
    with engine.begin() as conn:
        for ddl in TRIGGERS.values():
            conn.execute(text(ddl))


def canonical(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_hash(
    *,
    ts: str,
    app: str | None,
    actor_id: str | None,
    action: str,
    record_type: str | None,
    record_id: str | None,
    request_id: str | None,
    diff: str,
    prev_hash: str,
) -> str:
    body = canonical(
        {
            "ts": ts,
            "app": app,
            "actor_id": actor_id,
            "action": action,
            "record_type": record_type,
            "record_id": record_id,
            "request_id": request_id,
            "diff": diff,
            "prev_hash": prev_hash,
        }
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds")


def last_hash(session: Session) -> str:
    row = session.execute(select(AuditEntry.hash).order_by(AuditEntry.id.desc()).limit(1)).first()
    return row[0] if row else GENESIS


def write(
    session: Session,
    *,
    app: str | None,
    actor_id: str | None,
    action: str,
    record_type: str | None = None,
    record_id: str | None = None,
    diff: dict[str, Any] | None = None,
    request_id: str | None = None,
    ts: str | None = None,
) -> AuditEntry:
    """Appends one entry inside the caller's transaction; the caller commits or rolls back with its change."""
    entry = build_entry(
        prev_hash=last_hash(session),
        app=app,
        actor_id=actor_id,
        action=action,
        record_type=record_type,
        record_id=record_id,
        diff=diff,
        request_id=request_id,
        ts=ts,
    )
    session.add(entry)
    session.flush()
    return entry


def build_entry(
    *,
    prev_hash: str,
    app: str | None,
    actor_id: str | None,
    action: str,
    record_type: str | None,
    record_id: str | None,
    diff: dict[str, Any] | None,
    request_id: str | None,
    ts: str | None = None,
) -> AuditEntry:
    ts = ts or now_iso()
    diff_text = canonical(diff or {})
    digest = compute_hash(
        ts=ts,
        app=app,
        actor_id=actor_id,
        action=action,
        record_type=record_type,
        record_id=record_id,
        request_id=request_id,
        diff=diff_text,
        prev_hash=prev_hash,
    )
    return AuditEntry(
        ts=ts,
        app=app,
        actor_id=actor_id,
        action=action,
        record_type=record_type,
        record_id=record_id,
        request_id=request_id,
        diff=diff_text,
        prev_hash=prev_hash,
        hash=digest,
    )


def record_refusal(
    db: Database,
    *,
    app: str | None,
    actor_id: str | None,
    code: str,
    record_type: str | None,
    record_id: str | None,
    request_id: str | None,
) -> None:
    """Records a 403 in its own transaction, independent of whatever the refused request rolled back."""
    with db.session() as session:
        write(
            session,
            app=app,
            actor_id=actor_id,
            action="security.denied",
            record_type=record_type,
            record_id=record_id,
            diff={"code": code},
            request_id=request_id,
        )
        session.commit()


def entries_for_record(app: str, record_type: str, record_id: str) -> Select:
    return select(AuditEntry).where(
        AuditEntry.app == app, AuditEntry.record_type == record_type, AuditEntry.record_id == record_id
    )


def verify(session: Session) -> dict[str, Any]:
    """Walks the whole chain in id order and reports the first entry whose hash or link does not match."""
    result, _, _ = _walk(session, after_id=0, prev=GENESIS, count=0)
    return result


def _walk(session: Session, *, after_id: int, prev: str, count: int) -> tuple[dict[str, Any], int, str]:
    """Checks entries with id > after_id, continuing from a chain already verified up to `prev`.

    Returns the result plus the id and hash of the last good entry, so the next walk can resume there.
    """
    last_id = after_id
    for entry in session.execute(
        select(AuditEntry)
        .where(AuditEntry.id > after_id)
        .order_by(AuditEntry.id)
        .execution_options(yield_per=1000)
    ).scalars():
        count += 1
        expected = compute_hash(
            ts=entry.ts,
            app=entry.app,
            actor_id=entry.actor_id,
            action=entry.action,
            record_type=entry.record_type,
            record_id=entry.record_id,
            request_id=entry.request_id,
            diff=entry.diff,
            prev_hash=entry.prev_hash,
        )
        if entry.prev_hash != prev:
            return (
                {"ok": False, "entries": count, "first_bad_id": entry.id, "reason": "broken link"},
                last_id,
                prev,
            )
        if expected != entry.hash:
            return (
                {"ok": False, "entries": count, "first_bad_id": entry.id, "reason": "hash mismatch"},
                last_id,
                prev,
            )
        prev = entry.hash
        last_id = entry.id
    return {"ok": True, "entries": count, "first_bad_id": None, "reason": None}, last_id, prev


class ChainVerifier:
    """Caches chain verification so public callers (the /health badge) never walk the whole log.

    `status` checks only entries appended since the last good one, and re-walks the full chain at most once
    every `full_interval` seconds (rows already verified can only change if someone drops the triggers).
    `full` always walks everything; `/audit/verify` uses it and refreshes the cache. One walk runs at a time.
    """

    def __init__(self, *, full_interval: float = 300.0, clock: Callable[[], float] = time.monotonic) -> None:
        self.full_interval = full_interval
        self._clock = clock
        self._lock = threading.Lock()
        self._result: dict[str, Any] | None = None
        self._last_id = 0
        self._last_hash = GENESIS
        self._full_at: float | None = None

    def full(self, session: Session) -> dict[str, Any]:
        with self._lock:
            return self._full(session)

    def status(self, session: Session) -> dict[str, Any]:
        """Cached result brought up to date incrementally; while another walk runs, the last result."""
        if not self._lock.acquire(blocking=self._result is None):
            return dict(self._result or {})
        try:
            if self._result is None or self._full_due():
                return self._full(session)
            if not self._result["ok"]:
                return dict(self._result)
            if not self._anchor_intact(session):
                return self._full(session)
            result, self._last_id, self._last_hash = _walk(
                session, after_id=self._last_id, prev=self._last_hash, count=self._result["entries"]
            )
            self._result = result
            return dict(result)
        finally:
            self._lock.release()

    def _full_due(self) -> bool:
        return self._full_at is None or self._clock() - self._full_at >= self.full_interval

    def _anchor_intact(self, session: Session) -> bool:
        # A reset database (e.g. `make seed` against a running API) restarts ids, so the cached tail is stale.
        if self._last_id == 0:
            return session.scalar(select(AuditEntry.id).limit(1)) is None
        return (
            session.scalar(select(AuditEntry.hash).where(AuditEntry.id == self._last_id)) == self._last_hash
        )

    def _full(self, session: Session) -> dict[str, Any]:
        result, self._last_id, self._last_hash = _walk(session, after_id=0, prev=GENESIS, count=0)
        self._result = result
        self._full_at = self._clock()
        return dict(result)
