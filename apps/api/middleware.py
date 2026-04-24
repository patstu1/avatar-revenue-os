"""Request-scoped middleware: correlation IDs, structured logging, security headers, global error handling."""

from __future__ import annotations

import time
import traceback
import uuid

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger()

REQUEST_ID_HEADER = "X-Request-ID"

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
}


class RedirectHostFixMiddleware(BaseHTTPMiddleware):
    """Rewrites Location headers on 307/308 redirects to use the client's
    original Host header instead of the internal Docker hostname.

    When behind a reverse proxy (Caddy/Next.js), FastAPI's redirect_slashes
    emits Location headers like ``http://api:8000/...`` which are unreachable
    from browsers. This middleware replaces the authority with the value from
    the incoming Host header so the redirect works end-to-end.
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if response.status_code in (307, 308) and "location" in response.headers:
            from urllib.parse import urlparse, urlunparse

            loc = response.headers["location"]
            parsed = urlparse(loc)
            client_host = request.headers.get("host", "")
            scheme = request.headers.get("x-forwarded-proto", request.scope.get("scheme", "http"))
            fixed = urlunparse((scheme, client_host, parsed.path, parsed.params, parsed.query, parsed.fragment))
            response.headers["location"] = fixed
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds standard security headers to every response."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        for header, value in SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        return response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Generates or propagates a request ID and binds it to structlog context."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get(REQUEST_ID_HEADER, str(uuid.uuid4()))
        request.state.request_id = request_id

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        start = time.perf_counter()
        logger.info(
            "request.start",
            method=request.method,
            path=request.url.path,
            client=request.client.host if request.client else None,
        )

        response = await call_next(request)

        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers[REQUEST_ID_HEADER] = request_id

        logger.info(
            "request.end",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=elapsed_ms,
        )

        structlog.contextvars.clear_contextvars()
        return response


def register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers that return sanitized JSON."""

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "unknown")
        logger.error(
            "unhandled_exception",
            exc_type=type(exc).__name__,
            exc_message=str(exc),
            path=request.url.path,
            traceback=traceback.format_exc(),
        )
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error",
                "request_id": request_id,
            },
            headers={REQUEST_ID_HEADER: request_id},
        )

    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "unknown")
        return JSONResponse(
            status_code=404,
            content={
                "detail": "Not found",
                "request_id": request_id,
            },
            headers={REQUEST_ID_HEADER: request_id},
        )
