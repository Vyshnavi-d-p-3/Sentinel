"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """All config from environment / .env file."""

    # Runtime
    environment: Literal["development", "staging", "production", "test"] = "development"

    # Database
    database_url: str = "postgresql+asyncpg://sentinel:sentinel@localhost:5432/sentinel"
    # In production we prefer Alembic-managed migrations; auto-create is for dev.
    db_auto_create_tables: bool = True

    # GitHub App
    github_app_id: str = ""
    github_private_key_path: str = "./private-key.pem"
    github_webhook_secret: str = ""

    # LLM
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    default_model: str = "claude-sonnet-4-20250514"
    fallback_model: str = "gpt-4o"
    # When True, never calls external LLM APIs (CI / local without keys).
    llm_mock_mode: bool = False
    # Hard wall-clock cap for one LLM call (per provider attempt). Prevents a
    # hung HTTP connection from pinning a worker forever.
    llm_call_timeout_sec: float = 60.0

    # Cost guard
    daily_token_budget: int = 100_000
    per_pr_token_cap: int = 20_000
    circuit_breaker_threshold: int = 3
    circuit_breaker_window_sec: int = 300

    # Retrieval
    voyageai_api_key: str = ""
    embedding_model: str = "voyage-code-3"
    embedding_dim: int = 1024
    retrieval_top_k: int = 5
    rrf_k: int = 60
    retrieval_per_source_top_k: int = 20
    retrieval_recency_boost_max: float = 0.1
    retrieval_recency_half_life_days: int = 365
    retrieval_context_token_budget: int = 6_000
    retrieval_diff_share: float = 0.6  # share of token budget reserved for the diff itself

    # Observability
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""

    # CORS
    cors_origins: list[str] = ["http://localhost:3000"]

    # ---- Security ---------------------------------------------------------
    # Optional API key required on /api/v1/* (dashboard) endpoints. When empty
    # the API is open — useful for local dev. In production, set this to a
    # high-entropy random string and configure the dashboard with the same key.
    api_key: str = ""
    # Hard cap on inbound request body bytes. 2 MiB is plenty for any sane
    # diff; larger uploads are rejected with HTTP 413.
    max_request_body_bytes: int = 2 * 1024 * 1024
    # Per-IP rate limits for the public + dashboard surface. Used by slowapi if
    # installed; silently ignored otherwise.
    rate_limit_default: str = "120/minute"
    rate_limit_webhook: str = "60/minute"
    rate_limit_preview: str = "10/minute"
    rate_limit_eval_trigger: str = "5/hour"

    # ---- Eval harness HTTP trigger (POST /api/v1/eval/trigger) ----------------
    # Disabled by default: spawning the eval runner is CPU-heavy and must never
    # be exposed on the public internet without API auth + strict limits.
    eval_trigger_enabled: bool = False
    eval_trigger_timeout_sec: float = 600.0
    # When True (recommended), the subprocess forces LLM_MOCK_MODE=true so a
    # mistaken trigger cannot burn provider quota.
    eval_trigger_force_mock: bool = True

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()


class ConfigValidationError(RuntimeError):
    """Raised at startup when production-mode config is missing required values."""


def validate_settings_for_runtime(s: Settings | None = None) -> list[str]:
    """
    Return a list of human-readable warnings about the current config.

    In ``production`` we additionally raise ``ConfigValidationError`` if any
    safety-critical setting is missing — better to crash on boot than silently
    accept webhooks with no signing secret.
    """
    s = s or settings
    warnings: list[str] = []
    errors: list[str] = []

    if not s.github_webhook_secret:
        msg = "GITHUB_WEBHOOK_SECRET is empty — incoming webhooks cannot be authenticated"
        (errors if s.environment == "production" else warnings).append(msg)

    has_llm_key = bool(s.anthropic_api_key.strip() or s.openai_api_key.strip())
    if not has_llm_key and not s.llm_mock_mode:
        msg = "No LLM API keys configured — set ANTHROPIC_API_KEY or OPENAI_API_KEY, or LLM_MOCK_MODE=true"
        (errors if s.environment == "production" else warnings).append(msg)

    if s.environment == "production":
        if s.db_auto_create_tables:
            warnings.append(
                "DB_AUTO_CREATE_TABLES is enabled in production — prefer Alembic migrations"
            )
        if not s.api_key:
            warnings.append(
                "API_KEY is empty in production — dashboard endpoints are unauthenticated"
            )
        if s.eval_trigger_enabled:
            warnings.append(
                "EVAL_TRIGGER_ENABLED is true — POST /api/v1/eval/trigger can spawn "
                "the eval runner; keep API_KEY set and monitor abuse"
            )
        if any(o.startswith("http://") and "localhost" not in o for o in s.cors_origins):
            warnings.append(
                "Non-localhost CORS origin uses http:// — production should use https://"
            )

    if errors:
        raise ConfigValidationError("; ".join(errors))
    return warnings
