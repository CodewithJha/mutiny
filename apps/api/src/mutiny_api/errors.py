"""Structured API errors — stable machine codes for clients/judges."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse


def error_body(
    *,
    code: str,
    message: str,
    status: int,
    request_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
            "status": status,
        }
    }
    if request_id:
        body["error"]["request_id"] = request_id
    if details:
        body["error"]["details"] = details
    return body


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    detail = exc.detail
    if isinstance(detail, dict) and "code" in detail:
        code = str(detail["code"])
        message = str(detail.get("message", detail))
        details = detail.get("details")
    else:
        code = _code_for_status(exc.status_code)
        message = str(detail)
        details = None
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(
            code=code,
            message=message,
            status=exc.status_code,
            request_id=request_id,
            details=details if isinstance(details, dict) else None,
        ),
        headers={"X-Request-Id": request_id} if request_id else None,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=500,
        content=error_body(
            code="internal_error",
            message="unexpected server error",
            status=500,
            request_id=request_id,
            details={"type": type(exc).__name__},
        ),
        headers={"X-Request-Id": request_id} if request_id else None,
    )


def _code_for_status(status: int) -> str:
    return {
        400: "bad_request",
        403: "forbidden",
        404: "not_found",
        409: "conflict",
        422: "validation_error",
        429: "rate_limited",
        500: "internal_error",
        503: "unavailable",
    }.get(status, "error")


def raise_api(
    status: int,
    code: str,
    message: str,
    *,
    details: dict[str, Any] | None = None,
) -> None:
    raise HTTPException(
        status_code=status,
        detail={"code": code, "message": message, "details": details or {}},
    )
