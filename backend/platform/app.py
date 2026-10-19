from __future__ import annotations

import re
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from backend.platform import audit, audit_routes, auth, health
from backend.platform.db import Database
from backend.platform.errors import install_error_handlers
from backend.platform.registry import AppManifest, Registry
from backend.platform.settings import Settings

REQUEST_ID_PATTERN = re.compile(r"[A-Za-z0-9-]{1,64}")


def resolve_request_id(supplied: str | None) -> str:
    if supplied is not None and REQUEST_ID_PATTERN.fullmatch(supplied):
        return supplied
    return uuid.uuid4().hex


def create_app(settings: Settings, manifests: list[AppManifest], *, create_schema: bool = True) -> FastAPI:
    app = FastAPI(title="Internal tools", version="0.1.0", docs_url="/docs" if settings.dev_mode else None)
    app.state.settings = settings
    app.state.db = Database(settings.database_url)
    app.state.registry = Registry(manifests)
    app.state.audit_chain = audit.ChainVerifier()
    app.state.refusals = audit.RefusalGate()
    if create_schema:
        app.state.db.create_schema()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-Id"],
    )

    @app.middleware("http")
    async def request_id(request: Request, call_next):
        request.state.request_id = resolve_request_id(request.headers.get("X-Request-Id"))
        response = await call_next(request)
        response.headers["X-Request-Id"] = request.state.request_id
        return response

    install_error_handlers(app)
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(audit_routes.router)
    for manifest in manifests:
        app.include_router(manifest.router)
    return app
