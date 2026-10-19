"""App registration, outside the foundation. Add a manifest here; API, seed, health and audit pick it up."""

from backend.apps.kyc.app import MANIFEST as KYC
from backend.platform.registry import AppManifest

MANIFESTS: list[AppManifest] = [KYC]
