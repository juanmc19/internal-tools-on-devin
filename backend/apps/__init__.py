"""App registration. Each app exports a `MANIFEST`; add it here to wire routes, Home card, health and seed."""

from backend.platform.registry import AppManifest

MANIFESTS: list[AppManifest] = []
