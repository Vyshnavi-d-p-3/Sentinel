"""Types returned by the review orchestrator."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.models.review_output import ReviewOutput


@dataclass(frozen=True)
class PipelineStepUsage:
    """Token + cost record for a single pipeline step (one cost_ledger row)."""

    step: str  # triage | review | crossref | synthesis
    model_version: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: int
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


@dataclass(frozen=True)
class OrchestratorResult:
    """Successful review run metadata + structured output + per-step telemetry."""

    output: ReviewOutput
    diff_hash: str
    prompt_hash: str
    model_version: str
    total_tokens: int
    input_tokens: int
    output_tokens: int
    latency_ms: int
    triage_result: dict[str, Any] | None = None
    pipeline_step_timings: dict[str, int] = field(default_factory=dict)
    step_usages: list[PipelineStepUsage] = field(default_factory=list)
    retrieval_ms: int = 0
