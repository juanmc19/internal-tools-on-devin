from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from fastapi import Request
from sqlalchemy import JSON, create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    type_annotation_map = {dict: JSON, list: JSON}


class Database:
    """One SQLite engine plus a session factory. Schema creation also installs the audit triggers."""

    def __init__(self, url: str) -> None:
        if url.startswith("sqlite:///") and not url.endswith(":memory:"):
            Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
        self.engine: Engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30})
        event.listen(self.engine, "connect", _sqlite_pragmas)
        event.listen(self.engine, "begin", _begin_immediate)
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False)
        # Read-only work (health, audit views, verify) gets its own engine that opens deferred transactions,
        # so it reads a WAL snapshot without taking the write lock that every writer queues on.
        if url.startswith("sqlite:///") and not url.endswith(":memory:"):
            self.read_engine: Engine = create_engine(
                url, connect_args={"check_same_thread": False, "timeout": 30}
            )
            event.listen(self.read_engine, "connect", _sqlite_read_pragmas)
            event.listen(self.read_engine, "begin", _begin_deferred)
            self.ReadSessionLocal = sessionmaker(bind=self.read_engine, expire_on_commit=False)
        else:
            self.read_engine = self.engine
            self.ReadSessionLocal = self.SessionLocal

    def create_schema(self) -> None:
        from backend.platform.audit import install_audit_triggers

        Base.metadata.create_all(self.engine)
        install_audit_triggers(self.engine)

    def session(self) -> Session:
        return self.SessionLocal()

    def read_session(self) -> Session:
        return self.ReadSessionLocal()


def _sqlite_pragmas(dbapi_conn, _record) -> None:
    # pysqlite only issues BEGIN at the first INSERT/UPDATE, so a transaction that reads the last audit hash
    # and then inserts could interleave with another writer. Disable its implicit transactions and open every
    # transaction ourselves with BEGIN IMMEDIATE (write lock from the start; concurrent writers queue up).
    dbapi_conn.isolation_level = None
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA foreign_keys=ON")
    cur.execute("PRAGMA synchronous=NORMAL")
    cur.close()


def _sqlite_read_pragmas(dbapi_conn, _record) -> None:
    dbapi_conn.isolation_level = None
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.execute("PRAGMA query_only=ON")
    cur.close()


def _begin_immediate(conn) -> None:
    conn.exec_driver_sql("BEGIN IMMEDIATE")


def _begin_deferred(conn) -> None:
    conn.exec_driver_sql("BEGIN DEFERRED")


def get_session(request: Request) -> Iterator[Session]:
    session = request.app.state.db.session()
    try:
        yield session
    finally:
        session.close()


def get_read_session(request: Request) -> Iterator[Session]:
    """A session for routes that never write: deferred transaction, `query_only`, no write lock."""
    session = request.app.state.db.read_session()
    try:
        yield session
    finally:
        session.close()
