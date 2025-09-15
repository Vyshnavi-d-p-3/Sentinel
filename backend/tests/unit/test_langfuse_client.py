"""Langfuse client factory (no network; disabled without API keys)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.observability.langfuse_client import get_langfuse, reset_langfuse_for_tests


@pytest.fixture(autouse=True)
def _reset() -> None:
    reset_langfuse_for_tests()
    yield
    reset_langfuse_for_tests()


def test_get_langfuse_none_without_keys() -> None:
    s = MagicMock()
    s.langfuse_public_key = ""
    s.langfuse_secret_key = ""
    s.langfuse_host = ""

    with patch("app.config.get_settings", return_value=s):
        assert get_langfuse() is None
