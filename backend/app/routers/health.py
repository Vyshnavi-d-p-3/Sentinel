"""Codebase health intelligence endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Query
from sqlalchemy import text

from app.core.database import async_session
from app.services.health_intelligence import HealthIntelligenceEngine, report_to_dict

router = APIRouter(prefix="/api/v1/health")
_engine = HealthIntelligenceEngine()


@router.get("/report")
async def health_report(days: int = Query(default=30, ge=1, le=365)):
    reviews = await _fetch_reviews(days)
    feedback = await _fetch_feedback(days)
    report = _engine.analyze(reviews, feedback, period_days=days)
    return report_to_dict(report)


@router.get("/hotspots")
async def health_hotspots(
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=10, ge=1, le=100),
):
    reviews = await _fetch_reviews(days)
    report = _engine.analyze(reviews, [], period_days=days)
    return {"hotspots": [h.__dict__ for h in report.hotspots[:limit]], "days": days}


@router.get("/trends")
async def health_trends(days: int = Query(default=90, ge=1, le=365)):
    reviews = await _fetch_reviews(days)
    report = _engine.analyze(reviews, [], period_days=days)
    return {"trends": report.trends, "days": days}


@router.get("/patterns")
async def health_patterns(
    days: int = Query(default=90, ge=1, le=365),
    limit: int = Query(default=10, ge=1, le=100),
):
    reviews = await _fetch_reviews(days)
    report = _engine.analyze(reviews, [], period_days=days)
    return {"patterns": [p.__dict__ for p in report.patterns[:limit]], "days": days}


@router.get("/modules")
async def health_modules(days: int = Query(default=30, ge=1, le=365)):
    reviews = await _fetch_reviews(days)
    report = _engine.analyze(reviews, [], period_days=days)
    return {"modules": [m.__dict__ for m in report.modules], "days": days}


@router.get("/impact")
async def health_impact(days: int = Query(default=30, ge=1, le=365)):
    feedback = await _fetch_feedback(days)
    report = _engine.analyze([], feedback, period_days=days)
    impact = report.impact.__dict__ if report.impact is not None else None
    return {"impact": impact, "days": days}


async def _fetch_reviews(days: int) -> list[dict[str, Any]]:
    since = datetime.utcnow() - timedelta(days=days)
    query = text(
        """
        SELECT
            id,
            repo_id,
            pr_number,
            pr_title,
            created_at,
            comments,
            total_tokens
        FROM reviews
        WHERE created_at >= :since
        ORDER BY created_at DESC
        """
    )
    async with async_session() as session:
        rows = (await session.execute(query, {"since": since})).mappings().all()
    return [dict(r) for r in rows]


async def _fetch_feedback(days: int) -> list[dict[str, Any]]:
    since = datetime.utcnow() - timedelta(days=days)
    query = text(
        """
        SELECT
            id,
            review_id,
            repo_id,
            action,
            category,
            severity,
            created_at
        FROM review_feedback
        WHERE created_at >= :since
        ORDER BY created_at DESC
        """
    )
    async with async_session() as session:
        rows = (await session.execute(query, {"since": since})).mappings().all()
    return [dict(r) for r in rows]
