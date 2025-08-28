"""Unit tests for the cost-router aggregation helper (pure-Python, no DB)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from app.routers.costs import _aggregate


def _row(
    *,
    cost: float,
    inp: int,
    out: int,
    step: str,
    model: str,
    created_at: datetime,
    review_id: str | None = None,
    repo_id: str | None = None,
) -> SimpleNamespace:
    """Minimal stand-in for a CostLedger ORM row."""
    return SimpleNamespace(
        id=uuid.uuid4(),
        review_id=review_id or str(uuid.uuid4()),
        repo_id=repo_id or str(uuid.uuid4()),
        cost_usd=cost,
        input_tokens=inp,
        output_tokens=out,
        pipeline_step=step,
        model_version=model,
        created_at=created_at,
    )


def test_aggregate_groups_by_day_step_and_model() -> None:
    now = datetime(2026, 4, 21, 12, 0, 0)
    yesterday = now - timedelta(days=1)
    review_a = str(uuid.uuid4())
    review_b = str(uuid.uuid4())

    rows = [
        # Two ledger entries for the same review (different steps) on 'today'.
        _row(cost=0.10, inp=100, out=50, step="triage", model="claude-sonnet-4",
             created_at=now, review_id=review_a),
        _row(cost=0.25, inp=300, out=100, step="deep_review", model="claude-sonnet-4",
             created_at=now, review_id=review_a),
        # Different review, same day — should count as a second review.
        _row(cost=0.05, inp=50, out=20, step="triage", model="gpt-4o",
             created_at=now, review_id=review_b),
        # Yesterday — separate bucket.
        _row(cost=0.40, inp=400, out=200, step="deep_review", model="claude-sonnet-4",
             created_at=yesterday, review_id=review_b),
    ]

    daily, by_step, by_model, totals = _aggregate(rows, days=3, end=now)

    # Daily is padded to (days+1) rows ending at ``end``.
    assert len(daily) == 4
    today_row = next(d for d in daily if d.date == now.date().isoformat())
    assert today_row.cost_usd == pytest.approx(0.40)
    assert today_row.input_tokens == 450
    assert today_row.output_tokens == 170
    assert today_row.reviews == 2

    yday_row = next(d for d in daily if d.date == yesterday.date().isoformat())
    assert yday_row.cost_usd == pytest.approx(0.40)
    assert yday_row.reviews == 1

    # By-step is sorted by cost desc.
    assert [s.step for s in by_step] == ["deep_review", "triage"]
    deep = next(s for s in by_step if s.step == "deep_review")
    assert deep.cost_usd == pytest.approx(0.65)
    assert deep.reviews == 2

    # By-model groups unique review counts, not ledger rows.
    assert {m.model_version: m.reviews for m in by_model} == {
        "claude-sonnet-4": 2,
        "gpt-4o": 1,
    }

    # Totals.
    assert totals["cost_usd"] == pytest.approx(0.80)
    assert totals["input_tokens"] == 850
    assert totals["output_tokens"] == 370
    assert totals["reviews"] == 2


def test_aggregate_handles_empty_rows() -> None:
    now = datetime(2026, 4, 21, 0, 0, 0)
    daily, by_step, by_model, totals = _aggregate([], days=1, end=now)

    assert len(daily) == 2
    assert all(d.cost_usd == 0.0 and d.reviews == 0 for d in daily)
    assert by_step == []
    assert by_model == []
    assert totals == {
        "cost_usd": 0.0,
        "input_tokens": 0,
        "output_tokens": 0,
        "reviews": 0,
    }


def test_aggregate_skips_rows_missing_timestamp() -> None:
    now = datetime(2026, 4, 21, 12, 0, 0)
    rows = [
        _row(cost=1.0, inp=10, out=5, step="triage", model="x", created_at=now),
        _row(cost=99.0, inp=10, out=5, step="triage", model="x", created_at=None),  # type: ignore[arg-type]
    ]

    _, _, _, totals = _aggregate(rows, days=1, end=now)
    assert totals["cost_usd"] == 1.0
