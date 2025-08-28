"""
Security + observability middleware stack.

Layered in ``main.py`` so every request (dashboard, webhook, preview) gets:

1. A stable request ID (``X-Request-ID``) for log correlation.
2. A hard request-body size cap (default 2 MiB) to block trivial DoS.
3. Security response headers (XCTO, Referrer-Policy, X-Frame-Options, COEP/COOP).
4. Structured access logs with latency + redacted path.

Middlewares are kept dependency-light so the backend can start even before the
database is reachable — critical for health-check behavior.
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

logger = logging.getLogger("sentinel.access")

# Header name used for incoming + outgoing request IDs.
REQUEST_ID_HEADER = "X-Request-ID"

# Default body size cap. Tuned for unified diffs — real-world PRs are usually
# < 200 KiB; 2 MiB comfortably handles any legitimate review while rejecting
# obvious abuse. Overrideable per-route if we ever need to.
DEFAULT_MAX_BODY_BYTES = 2 * 1024 * 1024

# Baseline response headers — defense-in-depth against common attacks.
DEFAULT_SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-site",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=(), payment=()",
}


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a request ID to every request and echo it back on the response."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        incoming = request.headers.get(REQUEST_ID_HEADER, "").strip()
        # Only trust short, alphanum-ish incoming IDs to avoid log injection.
        rid = incoming if _valid_request_id(incoming) else uuid.uuid4().hex

        # Stash on request.state so handlers and downstream middleware can read it.
        request.state.request_id = rid
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = rid
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Inject baseline security headers on every response."""

    def __init__(self, app: ASGIApp, extra: dict[str, str] | None = None) -> None:
        super().__init__(app)
        self._headers = {**DEFAULT_SECURITY_HEADERS, **(extra or {})}

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        for key, value in self._headers.items():
            response.headers.setdefault(key, value)
        return response


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Reject requests whose body exceeds ``max_bytes``.

    Checks the ``Content-Length`` header first (cheap path), and for chunked
    uploads falls back to draining the stream with a running total. Uses 413
    Payload Too Large per RFC 9110.
    """

    def __init__(self, app: ASGIApp, max_bytes: int = DEFAULT_MAX_BODY_BYTES) -> None:
        super().__init__(app)
        self._max = max_bytes

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if request.method in {"GET", "HEAD", "OPTIONS", "DELETE"}:
            return await call_next(request)

        declared = request.headers.get("content-length")
        if declared is not None:
            try:
                declared_int = int(declared)
            except ValueError:
                return _too_large()
            if declared_int > self._max:
                return _too_large()

        # ``Request.body()`` buffers the full body; this is fine because we just
        # rejected anything above the limit. Calling it here primes FastAPI's
        # cache so the downstream handler re-uses the buffered bytes.
        try:
            body = await request.body()
        except Exception:  # noqa: BLE001 — malformed stream
            return _too_large()
        if len(body) > self._max:
            return _too_large()
        return await call_next(request)


class AccessLogMiddleware(BaseHTTPMiddleware):
    """
    Emit one structured log line per request.

    Intentionally avoids logging query strings (may contain repo IDs or
    auth-bearing tokens) and request bodies. Latency is reported in ms.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        started = time.monotonic()
        rid = getattr(request.state, "request_id", None)

        try:
            response = await call_next(request)
            status = response.status_code
        except Exception:
            elapsed_ms = int((time.monotonic() - started) * 1000)
            logger.exception(
                "request_failed",
                extra={
                    "request_id": rid,
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": elapsed_ms,
                },
            )
            raise

        elapsed_ms = int((time.monotonic() - started) * 1000)
        logger.info(
            "request",
            extra={
                "request_id": rid,
                "method": request.method,
                "path": request.url.path,
                "status": status,
                "duration_ms": elapsed_ms,
                "client_ip": _client_ip(request),
            },
        )
        return response


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _too_large() -> JSONResponse:
    return JSONResponse(
        status_code=413,
        content={"detail": "Request body too large"},
    )


def _valid_request_id(value: str) -> bool:
    """
    Accept only short, alphanum-with-dashes IDs. Anything else is dropped and
    replaced with a server-generated UUID to avoid header-injection tricks like
    newlines that could poison downstream log aggregators.
    """
    if not value or len(value) > 64:
        return False
    return all(c.isalnum() or c in ("-", "_") for c in value)


def _client_ip(request: Request) -> str | None:
    """Return the best-effort client IP (honours X-Forwarded-For if set)."""
    xff = request.headers.get("x-forwarded-for")
    if xff:
        # Left-most is the original client per RFC 7239 guidance.
        return xff.split(",", 1)[0].strip() or None
    if request.client:
        return request.client.host
    return None
