"""`make seed`: resets the database in place and runs every registered app's seed."""

from __future__ import annotations

import time

from sqlalchemy import MetaData

from backend.apps import MANIFESTS
from backend.platform.db import Database
from backend.platform.settings import Settings


def main() -> None:
    settings = Settings.from_env()
    db = Database(settings.database_url)
    # Drop every table in the existing file instead of deleting the file: a running API keeps its pooled
    # connections open, and a deleted file stays readable through them, so it would serve stale data.
    existing = MetaData()
    existing.reflect(bind=db.engine)
    existing.drop_all(bind=db.engine)
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
