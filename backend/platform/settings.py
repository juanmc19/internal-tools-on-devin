from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = BACKEND_DIR / "data" / "app.db"


@dataclass(frozen=True)
class Settings:
    app_env: str = "prod"
    database_url: str = f"sqlite:///{DEFAULT_DB_PATH}"

    @property
    def dev_mode(self) -> bool:
        return self.app_env == "dev"

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            app_env=os.environ.get("APP_ENV", "prod"),
            database_url=os.environ.get("DATABASE_URL", cls.database_url),
        )
