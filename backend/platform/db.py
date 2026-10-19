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
        self.engine: Engine = create_engine(url, connect_args={"check_same_thread": False})
        event.listen(self.engine, "connect", _sqlite_pragmas)
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False)

    def create_schema(self) -> None:
        from backend.platform.audit import install_audit_triggers

        Base.metadata.create_all(self.engine)
        install_audit_triggers(self.engine)

    def session(self) -> Session:
        return self.SessionLocal()


def _sqlite_pragmas(dbapi_conn, _record) -> None:
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA foreign_keys=ON")
    cur.execute("PRAGMA synchronous=NORMAL")
    cur.close()


def get_session(request: Request) -> Iterator[Session]:
    session = request.app.state.db.session()
    try:
        yield session
    finally:
        session.close()
