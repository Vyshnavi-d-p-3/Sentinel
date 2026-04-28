"""
Cost guard — budget enforcement and circuit breaker for LLM calls.

Three-layer protection:
1. Daily budget — total tokens across all PRs per repo
2. Per-PR cap — single PR cannot consume disproportionate budget
3. Circuit breaker — consecutive failures trigger cooldown (skip reviews)
"""

import time
from collections import deque
from dataclasses import dataclass


@dataclass
class CostGuardConfig:
    daily_token_budget: int = 100_000
    per_pr_token_cap: int = 20_000
    circuit_breaker_threshold: int = 3
    circuit_breaker_window_sec: int = 300

# The 3-failure threshold was tuned during load testing (Story 4 in
# engineering stories). At 5 failures, we were burning too many tokens
# on retries. At 2, legitimate transient errors triggered false opens.

class CostGuard:
    """
    Enforces cost limits on LLM usage.

    Usage:
        guard = CostGuard()
        allowed, reason = guard.can_review(repo_id, estimated_tokens=5000)
        if not allowed:
            logger.warning(f"Review skipped: {reason}")
            return
        # ... do review ...
        guard.record_usage(repo_id, actual_tokens)
    """

    def __init__(self, config: CostGuardConfig | None = None):
        self.config = config or CostGuardConfig()
        self._daily_usage: dict[str, int] = {}
        self._failures: deque[float] = deque()

    def can_review(self, repo_id: str, estimated_tokens: int) -> tuple[bool, str]:
        """Check all three guard layers. Returns (allowed, reason)."""
        if self._is_circuit_open():
            return False, "Circuit breaker open — too many recent failures"

        used = self._daily_usage.get(repo_id, 0)
        if used + estimated_tokens > self.config.daily_token_budget:
            return False, f"Daily budget exhausted: {used}/{self.config.daily_token_budget}"

        if estimated_tokens > self.config.per_pr_token_cap:
            return False, f"PR exceeds cap: {estimated_tokens} > {self.config.per_pr_token_cap}"

        return True, "ok"

    def record_usage(self, repo_id: str, tokens: int) -> None:
        """Record tokens consumed after successful review."""
        self._daily_usage[repo_id] = self._daily_usage.get(repo_id, 0) + tokens

    def record_failure(self) -> None:
        """Record a failed LLM call for circuit breaker."""
        self._failures.append(time.time())

    def get_daily_usage(self, repo_id: str) -> int:
        """Current daily token usage for a repo."""
        return self._daily_usage.get(repo_id, 0)

    def get_budget_remaining(self, repo_id: str) -> int:
        """Tokens remaining in daily budget."""
        return self.config.daily_token_budget - self.get_daily_usage(repo_id)

    def _is_circuit_open(self) -> bool:
        now = time.time()
        cutoff = now - self.config.circuit_breaker_window_sec
        while self._failures and self._failures[0] < cutoff:
            self._failures.popleft()
        return len(self._failures) >= self.config.circuit_breaker_threshold

    def reset_daily(self) -> None:
        """Reset all daily counters. Called by scheduler at midnight UTC."""
        self._daily_usage.clear()
