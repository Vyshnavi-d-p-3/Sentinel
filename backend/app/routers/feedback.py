"""Feedback endpoints — agreement-rate stats and recent feedback events."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.core.database import async_session
from app.core.timeutil import utc_now_naive
from app.services.feedback_tracker import (
    compute_category_agreement,
    compute_daily_agreement,
    compute_overall_agreement,
    count_feedback_actions,
    fetch_feedback_rows,
)

router = APIRouter()


class FeedbackEvent(BaseModel):
    id: str
    review_id: str
    repo_id: str
    action: str
    category: str | None = None
    severity: str | None = None
    comment_index: int | None = None
    github_user: str | None = None
    reply_body: str | None = None
    created_at: datetime


class CategoryStat(BaseModel):
    category: str
    resolved: int
    dismissed: int
    replied: int
    agreement_rate: float = Field(ge=0.0, le=1.0)
    total: int


class DayStat(BaseModel):
    date: str
    resolved: int
    dismissed: int
    replied: int
    agreement_rate: float = Field(ge=0.0, le=1.0)


class FeedbackStatsResponse(BaseModel):
    window_days: int
    total_events: int
    resolved: int
    dismissed: int
    replied: int
    thumbs_up: int
    thumbs_down: int
    agreement_rate: float = Field(ge=0.0, le=1.0)
    by_category: list[CategoryStat]
    by_day: list[DayStat]
    counts_by_action: dict[str, int]


@router.get("/stats", response_model=FeedbackStatsResponse)
async def feedback_stats(
    repo_id: str | None = Query(default=None, description="Filter to a single repo (UUID)"),
    days: int = Query(default=30, ge=1, le=365, description="Window for daily aggregation"),
):
    """Aggregate online feedback stats across the requested window."""
    since = utc_now_naive() - timedelta(days=days)
    rows = await _load_rows(repo_id=repo_id, since=since)

    overall: dict[str, Any] = compute_overall_agreement(rows)
    category_breakdown = compute_category_agreement(rows)
    daily_series = compute_daily_agreement(rows, days=days)
    counts_by_action = await _action_counts(repo_id=repo_id)

    return FeedbackStatsResponse(
        window_days=days,
        total_events=int(overall["total_events"]),
        resolved=int(overall["resolved"]),
        dismissed=int(overall["dismissed"]),
        replied=int(overall["replied"]),
        thumbs_up=int(overall["thumbs_up"]),
        thumbs_down=int(overall["thumbs_down"]),
        agreement_rate=float(overall["agreement_rate"]),
        by_category=[CategoryStat(**row) for row in category_breakdown],
        by_day=[DayStat(**row) for row in daily_series],
        counts_by_action=counts_by_action,
    )


@router.get("/recent", response_model=list[FeedbackEvent])
async def recent_feedback(
    repo_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
):
    """Most recent feedback events, newest first."""
    rows = await _load_rows(repo_id=repo_id, since=None, limit=limit)
    return [
        FeedbackEvent(
            id=str(row.id),
            review_id=str(row.review_id),
            repo_id=str(row.repo_id),
            action=row.action,
            category=row.category,
            severity=row.severity,
            comment_index=row.comment_index,
            github_user=row.github_user,
            reply_body=row.reply_body,
            created_at=row.created_at,
        )
        for row in rows
    ]


async def _load_rows(*, repo_id: str | None, since: datetime | None, limit: int | None = None):
    async with async_session() as session:
        return await fetch_feedback_rows(
            session,
            repo_id=repo_id,
            since=since,
            limit=limit,
        )


async def _action_counts(*, repo_id: str | None) -> dict[str, int]:
    async with async_session() as session:
        return await count_feedback_actions(session, repo_id=repo_id)
