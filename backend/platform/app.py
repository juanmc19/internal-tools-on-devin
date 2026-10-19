from __future__ import annotations

import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from backend.platform import audit, audit_routes, auth, health
from backend.platform.db import Database
from backend.platform.errors import install_error_handlers
from backend.platform.registry import AppManifest, Registry
from backend.platform.settings import Settings


def create_app(settings: Settings, manifests: list[AppManifest], *, create_schema: bool = True) -> FastAPI:
    app = FastAPI(title="Internal tools", version="0.1.0", docs_url="/docs" if settings.dev_mode else None)
    app.state.settings = settings
    app.state.db = Database(settings.database_url)
    app.state.registry = Registry(manifests)
    app.state.audit_chain = audit.ChainVerifier()
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
        request.state.request_id = request.headers.get("X-Request-Id") or uuid.uuid4().hex[:16]
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
