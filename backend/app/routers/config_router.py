"""Config endpoint — surfaces the effective runtime knobs for the dashboard.

Returns a **sanitized** view of ``settings`` (no secrets) plus the current
in-memory prompt hash and a few derived flags (mock mode, budget, retrieval
params). Used by the dashboard's Settings page.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import settings
from app.prompts.review_prompts import review_prompt_template_hash

router = APIRouter()


class LLMConfig(BaseModel):
    default_model: str
    fallback_model: str
    mock_mode: bool
    has_anthropic_key: bool
    has_openai_key: bool


class CostGuardConfig(BaseModel):
    daily_token_budget: int
    per_pr_token_cap: int
    circuit_breaker_threshold: int
    circuit_breaker_window_sec: int


class RetrievalConfig(BaseModel):
    embedding_model: str
    embedding_dim: int
    top_k: int
    rrf_k: int
    per_source_top_k: int
    recency_boost_max: float
    recency_half_life_days: int
    context_token_budget: int
    diff_share: float
    has_voyage_key: bool


class ObservabilityConfig(BaseModel):
    has_langfuse_keys: bool


class GithubConfig(BaseModel):
    app_id_configured: bool
    webhook_secret_configured: bool
    private_key_path: str


class EvalHarnessConfig(BaseModel):
    """Whether POST /eval/trigger is allowed (operators opt in via env)."""

    remote_trigger_enabled: bool
    trigger_force_mock: bool
    trigger_timeout_sec: float


class ConfigResponse(BaseModel):
    version: str
    prompt_hash: str
    llm: LLMConfig
    cost_guard: CostGuardConfig
    retrieval: RetrievalConfig
    observability: ObservabilityConfig
    github: GithubConfig
    eval: EvalHarnessConfig  # noqa: A003 — JSON field name required by dashboard contract
    cors_origins: list[str]


def _truthy(value: str | None) -> bool:
    return bool(value and value.strip())


@router.get("/", response_model=ConfigResponse)
async def get_config() -> ConfigResponse:
    """Return a redacted snapshot of the effective runtime configuration."""
    return ConfigResponse(
        version="0.1.0",
        prompt_hash=review_prompt_template_hash(),
        llm=LLMConfig(
            default_model=settings.default_model,
            fallback_model=settings.fallback_model,
            mock_mode=bool(settings.llm_mock_mode),
            has_anthropic_key=_truthy(settings.anthropic_api_key),
            has_openai_key=_truthy(settings.openai_api_key),
        ),
        cost_guard=CostGuardConfig(
            daily_token_budget=int(settings.daily_token_budget),
            per_pr_token_cap=int(settings.per_pr_token_cap),
            circuit_breaker_threshold=int(settings.circuit_breaker_threshold),
            circuit_breaker_window_sec=int(settings.circuit_breaker_window_sec),
        ),
        retrieval=RetrievalConfig(
            embedding_model=settings.embedding_model,
            embedding_dim=int(settings.embedding_dim),
            top_k=int(settings.retrieval_top_k),
            rrf_k=int(settings.rrf_k),
            per_source_top_k=int(settings.retrieval_per_source_top_k),
            recency_boost_max=float(settings.retrieval_recency_boost_max),
            recency_half_life_days=int(settings.retrieval_recency_half_life_days),
            context_token_budget=int(settings.retrieval_context_token_budget),
            diff_share=float(settings.retrieval_diff_share),
            has_voyage_key=_truthy(settings.voyageai_api_key),
        ),
        observability=ObservabilityConfig(
            has_langfuse_keys=_truthy(settings.langfuse_public_key)
            and _truthy(settings.langfuse_secret_key),
        ),
        github=GithubConfig(
            app_id_configured=_truthy(settings.github_app_id),
            webhook_secret_configured=_truthy(settings.github_webhook_secret),
            private_key_path=settings.github_private_key_path,
        ),
        eval=EvalHarnessConfig(
            remote_trigger_enabled=bool(settings.eval_trigger_enabled),
            trigger_force_mock=bool(settings.eval_trigger_force_mock),
            trigger_timeout_sec=float(settings.eval_trigger_timeout_sec),
        ),
        cors_origins=list(settings.cors_origins),
    )
