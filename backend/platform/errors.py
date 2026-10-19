from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ApiError(Exception):
    """A refusal or failure the API returns as `{"code", "message"}`.

    403s are recorded in the audit log (in their own transaction) by the error handler,
    so every refusal is both visible to the caller and kept for oversight.
    """

    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        *,
        app: str | None = None,
        record_type: str | None = None,
        record_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.app = app
        self.record_type = record_type
        self.record_id = record_id


def not_found(record_type: str = "record") -> ApiError:
    return ApiError(404, "NOT_FOUND", f"No such {record_type}.")


def install_error_handlers(app: FastAPI) -> None:
    from backend.platform.audit import record_refusal

    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError) -> JSONResponse:
        if exc.status == 403:
            user = getattr(request.state, "user", None)
            record_refusal(
                request.app.state.db,
                app=exc.app,
                actor_id=user.id if user else None,
                code=exc.code,
                record_type=exc.record_type,
                record_id=exc.record_id,
                request_id=getattr(request.state, "request_id", None),
            )
        return JSONResponse(status_code=exc.status, content={"code": exc.code, "message": exc.message})

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        loc = ".".join(str(p) for p in first.get("loc", []) if p != "body")
        message = f"{loc}: {first.get('msg', 'invalid request')}" if loc else "Invalid request."
        return JSONResponse(status_code=422, content={"code": "VALIDATION_ERROR", "message": message})
