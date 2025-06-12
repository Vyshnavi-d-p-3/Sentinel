"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """All config from environment / .env file."""

    # Database
    database_url: str = "postgresql+asyncpg://sentinel:sentinel@localhost:5432/sentinel"

    # GitHub App
    github_app_id: str = ""
    github_private_key_path: str = "./private-key.pem"
    github_webhook_secret: str = ""

    # LLM
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    default_model: str = "claude-sonnet-4-20250514"
    fallback_model: str = "gpt-4o"

    # Cost guard
    daily_token_budget: int = 100_000
    per_pr_token_cap: int = 20_000
    circuit_breaker_threshold: int = 3
    circuit_breaker_window_sec: int = 300

    # Retrieval
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536
    retrieval_top_k: int = 5
    rrf_k: int = 60

    # Observability
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""

    # CORS
    cors_origins: list[str] = ["http://localhost:3000"]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
