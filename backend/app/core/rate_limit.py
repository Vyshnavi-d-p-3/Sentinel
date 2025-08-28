"""
Per-IP rate limiting wrapper around ``slowapi``.

slowapi is an optional dependency; if it isn't installed we expose a no-op
``limiter`` so the rest of the app keeps working (useful for the slim CI
container and for unit tests). Real deployments install ``slowapi`` and limits
take effect automatically.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


def _client_ip(request: Any) -> str:
    """Return the best-effort client IP, honouring X-Forwarded-For."""
    xff = request.headers.get("x-forwarded-for") if hasattr(request, "headers") else None
    if xff:
        return xff.split(",", 1)[0].strip() or "unknown"
    if getattr(request, "client", None):
        return request.client.host
    return "unknown"


class _NullLimiter:
    """Fallback limiter used when ``slowapi`` is unavailable."""

    enabled = False

    def limit(self, *_args: Any, **_kwargs: Any) -> Callable[[Callable], Callable]:
        def decorator(func: Callable) -> Callable:
            return func

        return decorator


try:
    from slowapi import Limiter
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware

    # ``headers_enabled`` would emit ``X-RateLimit-*`` response headers but
    # requires every decorated endpoint to expose a ``response: Response``
    # parameter (slowapi rewrites the response object to inject headers).
    # Our handlers return plain dicts / Pydantic models, so we disable this
    # and rely on the 429 response body + server logs for observability.
    limiter = Limiter(
        key_func=_client_ip,
        default_limits=[settings.rate_limit_default],
        headers_enabled=False,
        strategy="fixed-window",
    )
    limiter.enabled = True  # type: ignore[attr-defined]
    SLOWAPI_AVAILABLE = True
except Exception as exc:  # noqa: BLE001 — best-effort optional dep
    logger.info("slowapi not available, rate limiting disabled: %s", exc)
    limiter = _NullLimiter()  # type: ignore[assignment]
    RateLimitExceeded = Exception  # type: ignore[assignment,misc]
    SlowAPIMiddleware = None  # type: ignore[assignment,misc]
    SLOWAPI_AVAILABLE = False


__all__ = ["limiter", "RateLimitExceeded", "SlowAPIMiddleware", "SLOWAPI_AVAILABLE"]
