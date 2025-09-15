"""Lazy Langfuse client — only constructed when project keys are configured."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langfuse import Langfuse

_lock = threading.Lock()
_client: Langfuse | None = None
_disabled_reason: str | None = None


def get_langfuse() -> Langfuse | None:
    """
    Return a shared ``Langfuse`` instance, or ``None`` if tracing is off.

    Tracing is enabled when both ``LANGFUSE_PUBLIC_KEY`` and
    ``LANGFUSE_SECRET_KEY`` are set (or non-empty in ``Settings``).
    """
    global _client, _disabled_reason
    if _client is not None or _disabled_reason is not None:
        return _client

    with _lock:
        if _client is not None or _disabled_reason is not None:
            return _client

        from app.config import get_settings

        s = get_settings()
        if not (s.langfuse_public_key.strip() and s.langfuse_secret_key.strip()):
            _disabled_reason = "no_keys"
            return None

        from langfuse import Langfuse

        host = s.langfuse_host.strip() or None
        _client = Langfuse(
            public_key=s.langfuse_public_key,
            secret_key=s.langfuse_secret_key,
            host=host,
        )
        return _client


def reset_langfuse_for_tests() -> None:
    """Test helper: clear cached client between tests."""
    global _client, _disabled_reason
    with _lock:
        _client = None
        _disabled_reason = None
