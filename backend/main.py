"""ASGI entry point: `uvicorn backend.main:app`. Registered apps live in backend/apps/__init__.py."""

from backend.apps import MANIFESTS
from backend.platform.app import create_app
from backend.platform.settings import Settings

app = create_app(Settings.from_env(), MANIFESTS)
