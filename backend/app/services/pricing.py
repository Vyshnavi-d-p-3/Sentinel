"""Rough USD cost from token counts (used for cost_ledger and dashboards)."""

from __future__ import annotations

# Per-million token rates (USD). Tune as provider pricing changes.
_CLAUDE_SONNET_INPUT_PER_M = 3.0
_CLAUDE_SONNET_OUTPUT_PER_M = 15.0
_GPT4O_INPUT_PER_M = 2.5
_GPT4O_OUTPUT_PER_M = 10.0


def estimate_llm_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    m = model.lower()
    if m == "mock":
        return 0.0
    if "gpt-4o" in m or "gpt4o" in m:
        inp, out = _GPT4O_INPUT_PER_M, _GPT4O_OUTPUT_PER_M
    elif "claude" in m:
        inp, out = _CLAUDE_SONNET_INPUT_PER_M, _CLAUDE_SONNET_OUTPUT_PER_M
    else:
        inp, out = _CLAUDE_SONNET_INPUT_PER_M, _CLAUDE_SONNET_OUTPUT_PER_M

    return (input_tokens / 1_000_000) * inp + (output_tokens / 1_000_000) * out


def split_estimated_tokens(total: int) -> tuple[int, int]:
    """Apportion rough total into input vs output for pricing when only total is known."""
    if total <= 0:
        return 0, 0
    # Heuristic: reviews are input-heavy.
    input_tokens = int(total * 0.72)
    output_tokens = max(0, total - input_tokens)
    return input_tokens, output_tokens
