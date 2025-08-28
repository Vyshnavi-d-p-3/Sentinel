"""Unit tests for the config router (no secrets in responses, shape parity)."""

from __future__ import annotations

import asyncio

from app.routers.config_router import _truthy, get_config


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def test_truthy_handles_empty_and_whitespace() -> None:
    assert _truthy(None) is False
    assert _truthy("") is False
    assert _truthy("   ") is False
    assert _truthy("anthropic-sk") is True


def test_config_endpoint_returns_redacted_snapshot() -> None:
    resp = _run(get_config())

    assert resp.version
    assert len(resp.prompt_hash) == 64  # sha256 hex

    # None of the raw secrets leak into the response, only has_* booleans.
    # We look for PEM headers / provider key prefixes that would only appear if
    # an actual credential leaked — not field names like ``private_key_path``.
    payload = resp.model_dump()
    as_text = repr(payload)
    for forbidden in ("sk-ant-", "sk-proj-", "BEGIN RSA", "BEGIN PRIVATE KEY"):
        assert forbidden not in as_text, f"Config response must not leak {forbidden!r}"

    # No raw key field names ever present in the response.
    for leaked_field in ("anthropic_api_key", "openai_api_key", "voyageai_api_key",
                         "github_webhook_secret", "langfuse_secret_key"):
        assert leaked_field not in payload
        for section in payload.values():
            if isinstance(section, dict):
                assert leaked_field not in section

    assert "has_anthropic_key" in payload["llm"]
    assert "has_openai_key" in payload["llm"]
    assert isinstance(payload["llm"]["mock_mode"], bool)

    cg = payload["cost_guard"]
    assert cg["daily_token_budget"] > 0
    assert cg["per_pr_token_cap"] > 0

    rt = payload["retrieval"]
    assert rt["embedding_dim"] > 0
    assert 0.0 <= rt["diff_share"] <= 1.0
    assert "has_voyage_key" in rt

    gh = payload["github"]
    assert "app_id_configured" in gh
    assert "webhook_secret_configured" in gh
    assert gh["private_key_path"]  # path itself is fine to expose

    assert isinstance(payload["cors_origins"], list)

    ev = payload["eval"]
    assert "remote_trigger_enabled" in ev
    assert "trigger_force_mock" in ev
    assert "trigger_timeout_sec" in ev
