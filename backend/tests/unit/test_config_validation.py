"""Tests for ``validate_settings_for_runtime``."""

from __future__ import annotations

import pytest

from app.config import ConfigValidationError, Settings, validate_settings_for_runtime


def _settings(**overrides) -> Settings:
    """Build a Settings instance with safe defaults so we test one knob at a time."""
    base = {
        "environment": "development",
        "github_webhook_secret": "secret",
        "anthropic_api_key": "",
        "openai_api_key": "",
        "llm_mock_mode": True,
    }
    base.update(overrides)
    return Settings(**base)


def test_dev_with_all_defaults_returns_no_warnings() -> None:
    assert validate_settings_for_runtime(_settings()) == []


def test_missing_webhook_secret_warns_in_dev() -> None:
    warnings = validate_settings_for_runtime(_settings(github_webhook_secret=""))
    assert any("WEBHOOK_SECRET" in w for w in warnings)


def test_missing_webhook_secret_errors_in_production() -> None:
    s = _settings(environment="production", github_webhook_secret="")
    with pytest.raises(ConfigValidationError):
        validate_settings_for_runtime(s)


def test_no_llm_keys_and_no_mock_mode_errors_in_production() -> None:
    s = _settings(environment="production", llm_mock_mode=False)
    with pytest.raises(ConfigValidationError):
        validate_settings_for_runtime(s)


def test_production_with_keys_and_secret_passes_with_warnings() -> None:
    s = _settings(
        environment="production",
        anthropic_api_key="9383ab45-2b27-49e2-8079-d9533cbc1b7c",
        llm_mock_mode=False,
        db_auto_create_tables=True,
        api_key="",
    )
    warnings = validate_settings_for_runtime(s)
    # Both warnings should fire (auto-create + missing API key) but neither
    # is a hard error.
    assert any("AUTO_CREATE" in w for w in warnings)
    assert any("API_KEY" in w for w in warnings)


def test_production_with_http_origin_warns() -> None:
    s = _settings(
        environment="production",
        anthropic_api_key="9383ab45-2b27-49e2-8079-d9533cbc1b7c",
        llm_mock_mode=False,
        api_key="real-key",
        cors_origins=["http://dashboard.example.com"],
        db_auto_create_tables=False,
    )
    warnings = validate_settings_for_runtime(s)
    assert any("https" in w.lower() for w in warnings)


def test_eval_trigger_enabled_warns_in_production() -> None:
    s = _settings(
        environment="production",
        anthropic_api_key="9383ab45-2b27-49e2-8079-d9533cbc1b7c",
        llm_mock_mode=False,
        api_key="k",
        eval_trigger_enabled=True,
    )
    warnings = validate_settings_for_runtime(s)
    assert any("EVAL_TRIGGER_ENABLED" in w for w in warnings)
