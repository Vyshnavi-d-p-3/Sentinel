"""
API-key authentication for the dashboard surface.

Behavior:

- If ``settings.api_key`` is empty, the dependency is a no-op (open API). This
  matches the local-dev experience and keeps demo deployments friction-free.
- If ``settings.api_key`` is set, every protected request must include either
  ``X-API-Key: <key>`` or ``Authorization: Bearer <key>``. We compare with
  ``hmac.compare_digest`` to avoid timing oracles.

The dependency is mounted at the router level (``api_v1_dependencies``) so the
``/webhook`` and ``/health`` endpoints stay open — webhooks are auth'd via HMAC
signature, and health is needed by load balancers.
"""

from __future__ import annotations

import hmac

from fastapi import Header, HTTPException, status

from app.config import settings


async def require_api_key(
    x_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> None:
    """FastAPI dependency: enforces the configured API key on dashboard routes."""
    expected = (settings.api_key or "").strip()
    if not expected:
        # Auth disabled — local dev / public demo. Caller is implicitly allowed.
        return

    presented = (x_api_key or "").strip()
    if not presented and authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() == "bearer":
            presented = token.strip()

    if not presented or not hmac.compare_digest(presented, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
