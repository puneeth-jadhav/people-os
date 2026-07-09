from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


def ok(data: Any = None) -> dict:
    return {"data": data}


def error_body(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


_STATUS_TO_CODE = {
    401: "UNAUTHENTICATED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    422: "VALIDATION",
}


class ApiError(HTTPException):
    """Raise with an explicit HTTP status; detail is used as the message."""

    def __init__(self, status_code: int, message: str, code: str | None = None):
        super().__init__(status_code=status_code, detail=message)
        self.code = code or _STATUS_TO_CODE.get(status_code, "ERROR")


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def _http_exc_handler(request: Request, exc: HTTPException):
        code = getattr(exc, "code", None) or _STATUS_TO_CODE.get(
            exc.status_code, "ERROR"
        )
        message = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        return JSONResponse(
            status_code=exc.status_code, content=error_body(code, message)
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content=error_body("VALIDATION", "Request validation failed"),
        )

    @app.exception_handler(Exception)
    async def _unhandled_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content=error_body("INTERNAL", "Internal server error"),
        )
