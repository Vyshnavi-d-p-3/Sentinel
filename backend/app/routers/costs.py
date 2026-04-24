"""Cost endpoints — daily breakdown, budget utilization, per-step LLM spend."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.config import settings
from app.core.database import async_session
from app.core.timeutil import utc_now_naive
from app.models.database import CostLedger, Repo
from app.services.pricing import estimate_llm_cost_usd

router = APIRouter()


_RANGE_DAYS = {"1d": 1, "7d": 7, "14d": 14, "30d": 30, "90d": 90}


class CostDailyRow(BaseModel):
    date: str
    cost_usd: float
    input_tokens: int
    output_tokens: int
    total_tokens: int
    reviews: int


class CostByStep(BaseModel):
    step: str
    cost_usd: float
    input_tokens: int
    output_tokens: int
    reviews: int


class CostByModel(BaseModel):
    model_version: str
    cost_usd: float
    reviews: int


class BudgetStatus(BaseModel):
    """Burn-rate against the configured daily budget."""

    daily_budget_usd: float | None = Field(default=None)
    today_cost_usd: float
    today_percent_of_budget: float = Field(ge=0.0)
    circuit_breaker_threshold: float | None = None


class CostSummaryResponse(BaseModel):
    range: str
    range_days: int
    total_cost_usd: float
    total_input_tokens: int
    total_output_tokens: int
    total_reviews: int
    daily: list[CostDailyRow]
    by_step: list[CostByStep]
    by_model: list[CostByModel]
    budget: BudgetStatus


def _range_days(range_: str) -> int:
    if range_ not in _RANGE_DAYS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid range {range_!r}; expected one of {sorted(_RANGE_DAYS)}",
        )
    return _RANGE_DAYS[range_]


def _parse_repo_id(repo_id: str | None) -> uuid.UUID | None:
    if repo_id is None:
        return None
    try:
        return uuid.UUID(repo_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid repo_id UUID") from exc


@router.get("/summary", response_model=CostSummaryResponse)
async def cost_summary(
    repo_id: str | None = Query(default=None),
    range: str = Query(default="7d"),  # noqa: A002 — matches existing contract
):
    """
    Aggregate LLM spend over ``range`` days with per-day, per-step, per-model
    breakdowns and today's progress against the configured daily budget.
    """
    days = _range_days(range)
    repo_uuid = _parse_repo_id(repo_id)
    now = utc_now_naive()
    since = now - timedelta(days=days)

    async with async_session() as session:
        base_filters = [CostLedger.created_at >= since]
        if repo_uuid is not None:
            base_filters.append(CostLedger.repo_id == repo_uuid)

        rows = (
            await session.execute(select(CostLedger).where(*base_filters))
        ).scalars().all()

        budget = await _budget_status(session, repo_uuid=repo_uuid, now=now)

    daily, by_step, by_model, totals = _aggregate(rows, days=days, end=now)

    return CostSummaryResponse(
        range=range,
        range_days=days,
        total_cost_usd=totals["cost_usd"],
        total_input_tokens=totals["input_tokens"],
        total_output_tokens=totals["output_tokens"],
        total_reviews=totals["reviews"],
        daily=daily,
        by_step=by_step,
        by_model=by_model,
        budget=budget,
    )


@router.get("/daily", response_model=list[CostDailyRow])
async def daily_costs(
    repo_id: str | None = Query(default=None),
    days: int = Query(default=30, ge=1, le=365),
):
    """Compact daily timeseries — just the per-day rows."""
    repo_uuid = _parse_repo_id(repo_id)
    now = utc_now_naive()
    since = now - timedelta(days=days)

    async with async_session() as session:
        filters = [CostLedger.created_at >= since]
        if repo_uuid is not None:
            filters.append(CostLedger.repo_id == repo_uuid)
        rows = (
            await session.execute(select(CostLedger).where(*filters))
        ).scalars().all()

    daily, _, _, _ = _aggregate(rows, days=days, end=now)
    return daily


# ---------------------------------------------------------------------------
# Aggregation helpers (pure Python — unit-testable without a DB)
# ---------------------------------------------------------------------------


def _aggregate(
    rows: list[CostLedger],
    *,
    days: int,
    end: datetime,
) -> tuple[list[CostDailyRow], list[CostByStep], list[CostByModel], dict[str, Any]]:
    """Fold raw CostLedger rows into the structured response shapes."""
    daily_buckets: dict[str, dict[str, Any]] = {}
    step_buckets: dict[str, dict[str, Any]] = {}
    model_buckets: dict[str, dict[str, Any]] = {}
    seen_review_ids_by_day: dict[str, set] = {}
    totals = {"cost_usd": 0.0, "input_tokens": 0, "output_tokens": 0, "reviews": set()}

    for row in rows:
        if row.created_at is None:
            continue
        day = row.created_at.date().isoformat()
        d = daily_buckets.setdefault(
            day,
            {"date": day, "cost_usd": 0.0, "input_tokens": 0, "output_tokens": 0,
             "total_tokens": 0, "reviews": 0},
        )
        d["cost_usd"] += float(row.cost_usd or 0.0)
        d["input_tokens"] += int(row.input_tokens or 0)
        d["output_tokens"] += int(row.output_tokens or 0)
        d["total_tokens"] = d["input_tokens"] + d["output_tokens"]

        # Count distinct reviews per day (avoid inflating count with per-step rows).
        review_key = str(row.review_id) if row.review_id is not None else f"noreview-{row.id}"
        day_reviews = seen_review_ids_by_day.setdefault(day, set())
        if review_key not in day_reviews:
            day_reviews.add(review_key)
            d["reviews"] += 1

        step = row.pipeline_step or "review"
        s = step_buckets.setdefault(
            step,
            {"step": step, "cost_usd": 0.0, "input_tokens": 0, "output_tokens": 0, "reviews": set()},
        )
        s["cost_usd"] += float(row.cost_usd or 0.0)
        s["input_tokens"] += int(row.input_tokens or 0)
        s["output_tokens"] += int(row.output_tokens or 0)
        s["reviews"].add(review_key)

        model = row.model_version or "unknown"
        m = model_buckets.setdefault(
            model,
            {"model_version": model, "cost_usd": 0.0, "reviews": set()},
        )
        m["cost_usd"] += float(row.cost_usd or 0.0)
        m["reviews"].add(review_key)

        totals["cost_usd"] += float(row.cost_usd or 0.0)
        totals["input_tokens"] += int(row.input_tokens or 0)
        totals["output_tokens"] += int(row.output_tokens or 0)
        totals["reviews"].add(review_key)

    # Pad daily to ``days`` entries so the chart has a steady x-axis.
    daily: list[CostDailyRow] = []
    for offset in range(days, -1, -1):
        day = (end - timedelta(days=offset)).date().isoformat()
        bucket = daily_buckets.get(day) or {
            "date": day,
            "cost_usd": 0.0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "reviews": 0,
        }
        daily.append(CostDailyRow(**bucket))

    by_step = [
        CostByStep(
            step=b["step"],
            cost_usd=b["cost_usd"],
            input_tokens=b["input_tokens"],
            output_tokens=b["output_tokens"],
            reviews=len(b["reviews"]),
        )
        for b in step_buckets.values()
    ]
    by_step.sort(key=lambda r: r.cost_usd, reverse=True)

    by_model = [
        CostByModel(
            model_version=b["model_version"],
            cost_usd=b["cost_usd"],
            reviews=len(b["reviews"]),
        )
        for b in model_buckets.values()
    ]
    by_model.sort(key=lambda r: r.cost_usd, reverse=True)

    totals_out = {
        "cost_usd": totals["cost_usd"],
        "input_tokens": totals["input_tokens"],
        "output_tokens": totals["output_tokens"],
        "reviews": len(totals["reviews"]),
    }
    return daily, by_step, by_model, totals_out


async def _budget_status(session, *, repo_uuid: uuid.UUID | None, now: datetime) -> BudgetStatus:
    """Compute today's cost and translate into budget/circuit-breaker terms."""
    midnight = datetime(now.year, now.month, now.day)

    filters = [CostLedger.created_at >= midnight]
    if repo_uuid is not None:
        filters.append(CostLedger.repo_id == repo_uuid)

    today_cost = float(
        (await session.execute(
            select(func.coalesce(func.sum(CostLedger.cost_usd), 0.0)).where(*filters)
        )).scalar() or 0.0
    )

    # Translate the token budget into USD via the same pricing module the ledger
    # uses so the percentage reflects reality.
    token_budget: int | None = None
    if repo_uuid is not None:
        row = (await session.execute(select(Repo).where(Repo.id == repo_uuid))).scalar_one_or_none()
        if row is not None and row.daily_token_budget:
            token_budget = int(row.daily_token_budget)
    else:
        token_budget = int(getattr(settings, "daily_token_budget", 0) or 0) or None

    daily_budget: float | None = None
    if token_budget:
        inp = int(token_budget * 0.72)
        out = max(0, token_budget - inp)
        daily_budget = estimate_llm_cost_usd(settings.default_model, inp, out)

    percent = 0.0
    if daily_budget and daily_budget > 0:
        percent = min(today_cost / daily_budget, 5.0)  # cap at 500% to avoid UI overflow

    return BudgetStatus(
        daily_budget_usd=daily_budget,
        today_cost_usd=today_cost,
        today_percent_of_budget=percent,
        circuit_breaker_threshold=getattr(settings, "circuit_breaker_threshold", None),
    )
