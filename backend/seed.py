"""`make seed`: recreates the database and runs every registered app's seed."""

from __future__ import annotations

import time
from pathlib import Path

from backend.apps import MANIFESTS
from backend.platform.db import Database
from backend.platform.settings import Settings


def main() -> None:
    settings = Settings.from_env()
    if settings.database_url.startswith("sqlite:///"):
        path = Path(settings.database_url.removeprefix("sqlite:///"))
        for suffix in ("", "-wal", "-shm"):
            Path(str(path) + suffix).unlink(missing_ok=True)
    db = Database(settings.database_url)
    db.create_schema()
    for manifest in MANIFESTS:
        if manifest.seed is None:
            continue
        started = time.perf_counter()
        with db.session() as session:
            manifest.seed(session)
            session.commit()
            count = manifest.count_records(session)
        print(f"{manifest.key}: seeded {count:,} records in {time.perf_counter() - started:.1f}s")
    print(f"database: {settings.database_url}")


if __name__ == "__main__":
    main()
