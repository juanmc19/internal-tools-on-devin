"""Apps register a manifest; the foundation wires routes, Home cards, health and seeding from it."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from fastapi import APIRouter
from sqlalchemy.orm import Session

from backend.platform.policy import Policy


@dataclass(frozen=True)
class AppManifest:
    key: str
    name: str
    owner_team: str
    description: str
    policy: Policy
    router: APIRouter
    web_path: str
    count_records: Callable[[Session], int]
    seed: Callable[[Session], None] | None = None
    record_type: str = "record"


class Registry:
    def __init__(self, manifests: list[AppManifest]) -> None:
        self._apps = {m.key: m for m in manifests}

    def get(self, key: str) -> AppManifest | None:
        return self._apps.get(key)

    def require(self, key: str) -> AppManifest:
        manifest = self._apps.get(key)
        if manifest is None:
            from backend.platform.errors import not_found

            raise not_found("app")
        return manifest

    def all(self) -> list[AppManifest]:
        return list(self._apps.values())
