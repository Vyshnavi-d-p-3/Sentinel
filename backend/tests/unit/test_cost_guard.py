"""Tests for CostGuard — budget enforcement and circuit breaker."""

import pytest

from app.services.cost_guard import CostGuard, CostGuardConfig


@pytest.fixture
def guard():
    return CostGuard(CostGuardConfig(
        daily_token_budget=10_000,
        per_pr_token_cap=5_000,
        circuit_breaker_threshold=2,
        circuit_breaker_window_sec=10,
    ))


class TestCostGuard:
    def test_allows_within_budget(self, guard):
        ok, reason = guard.can_review("repo-1", 3000)
        assert ok is True

    def test_blocks_over_daily_budget(self, guard):
        guard.record_usage("repo-1", 8000)
        ok, reason = guard.can_review("repo-1", 3000)
        assert ok is False
        assert "budget" in reason.lower()

    def test_blocks_over_pr_cap(self, guard):
        ok, reason = guard.can_review("repo-1", 6000)
        assert ok is False
        assert "cap" in reason.lower()

    def test_circuit_breaker_opens(self, guard):
        guard.record_failure()
        guard.record_failure()
        ok, reason = guard.can_review("repo-1", 100)
        assert ok is False
        assert "circuit" in reason.lower()

    def test_reset_daily(self, guard):
        guard.record_usage("repo-1", 9000)
        guard.reset_daily()
        ok, _ = guard.can_review("repo-1", 3000)
        assert ok is True

    def test_budget_remaining(self, guard):
        guard.record_usage("repo-1", 4000)
        assert guard.get_budget_remaining("repo-1") == 6000
