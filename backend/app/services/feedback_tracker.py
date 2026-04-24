"""
Online feedback tracker.

Captures developer reactions to Sentinel's PR comments from GitHub webhook
payloads and turns them into ``review_feedback`` rows. Also exposes stat
aggregations consumed by the dashboard's feedback page:

- agreement-rate trend over time (resolved / (resolved + dismissed))
- per-category agreement rate (which categories devs find valuable)
- most-dismissed categories (drives prompt iteration)
- recent feedback events (for manual inspection)

The capture path is idempotent: GitHub frequently re-delivers webhook events,
and ``ReviewFeedback`` has a uniqueness constraint on
``(review_id, github_comment_id, action)`` so retries are safe.
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timeutil import utc_now_naive
from app.models.database import Repo, Review, ReviewFeedback

logger = logging.getLogger(__name__)


# Action vocabulary — also referenced by the model docstring and tests.
ACTION_DISMISSED = "dismissed"
ACTION_RESOLVED = "resolved"
ACTION_REPLIED = "replied"
ACTION_THUMBS_UP = "thumbs_up"
ACTION_THUMBS_DOWN = "thumbs_down"

POSITIVE_ACTIONS: frozenset[str] = frozenset({ACTION_RESOLVED, ACTION_THUMBS_UP})
NEGATIVE_ACTIONS: frozenset[str] = frozenset({ACTION_DISMISSED, ACTION_THUMBS_DOWN})


# ---------------------------------------------------------------------------
# Inbound webhook → feedback row
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ParsedFeedback:
    """A normalized feedback event extracted from a GitHub webhook payload."""

    action: str
    repo_full_name: str
    pr_number: int
    github_user: str | None
    github_comment_id: str | None
    github_review_id: str | None
    reply_body: str | None
    inline_path: str | None
    inline_line: int | None


def parse_pull_request_review_event(payload: dict[str, Any]) -> ParsedFeedback | None:
    """Parse ``pull_request_review`` (review-level dismiss/submit)."""
    action = str(payload.get("action") or "").lower()
    if action != "dismissed":
        return None  # only "dismissed" is meaningful at review level
    review = payload.get("review") or {}
    pr = payload.get("pull_request") or {}
    repo = payload.get("repository") or {}
    return ParsedFeedback(
        action=ACTION_DISMISSED,
        repo_full_name=str(repo.get("full_name") or ""),
        pr_number=int(pr.get("number") or 0),
        github_user=str((review.get("user") or {}).get("login") or "") or None,
        github_comment_id=None,
        github_review_id=str(review.get("id")) if review.get("id") is not None else None,
        reply_body=None,
        inline_path=None,
        inline_line=None,
    )


def parse_pull_request_review_comment_event(payload: dict[str, Any]) -> ParsedFeedback | None:
    """Parse ``pull_request_review_comment`` (replies and resolutions on inline comments)."""
    action = str(payload.get("action") or "").lower()
    comment = payload.get("comment") or {}
    pr = payload.get("pull_request") or {}
    repo = payload.get("repository") or {}

    # GitHub fires "created" for both new comments and replies; we treat any
    # in_reply_to_id-bearing payload as a reply.
    if action == "created":
        if not comment.get("in_reply_to_id"):
            return None  # ignore primary comments not authored by Sentinel
        action_norm = ACTION_REPLIED
    elif action in {"resolved", "marked_as_resolved"}:
        action_norm = ACTION_RESOLVED
    else:
        return None

    target_comment_id = comment.get("in_reply_to_id") or comment.get("id")
    return ParsedFeedback(
        action=action_norm,
        repo_full_name=str(repo.get("full_name") or ""),
        pr_number=int(pr.get("number") or 0),
        github_user=str((comment.get("user") or {}).get("login") or "") or None,
        github_comment_id=str(target_comment_id) if target_comment_id is not None else None,
        github_review_id=str(comment.get("pull_request_review_id"))
            if comment.get("pull_request_review_id") is not None
            else None,
        reply_body=str(comment.get("body") or "") or None,
        inline_path=str(comment.get("path") or "") or None,
        inline_line=int(comment["line"]) if isinstance(comment.get("line"), int) else None,
    )


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


async def _find_target_review(
    session: AsyncSession,
    *,
    parsed: ParsedFeedback,
) -> Review | None:
    """Locate the Sentinel review the feedback applies to."""
    if not parsed.repo_full_name or parsed.pr_number <= 0:
        return None
    repo_q = await session.execute(select(Repo).where(Repo.full_name == parsed.repo_full_name))
    repo = repo_q.scalar_one_or_none()
    if repo is None:
        return None
    review_q = await session.execute(
        select(Review)
        .where(Review.repo_id == repo.id, Review.pr_number == parsed.pr_number)
        .order_by(desc(Review.created_at))
        .limit(1)
    )
    return review_q.scalar_one_or_none()


def _locate_comment_index(
    review: Review,
    *,
    github_comment_id: str | None,
    inline_path: str | None,
    inline_line: int | None,
) -> tuple[int | None, str | None, str | None]:
    """
    Find which comment in ``review.comments`` the feedback applies to.

    Strategy:
    - Prefer matching GitHub comment id stored in ``review.github_review_id``
      (csv of GitHub comment ids in the same order as ``review.comments``).
    - Otherwise fall back to (path, line) match against ``review.comments``.

    Returns ``(comment_index, category, severity)`` — any field may be None
    when the lookup cannot resolve a specific comment (e.g. review-level
    dismiss).
    """
    comments = review.comments or []
    if not comments:
        return None, None, None

    if github_comment_id and review.github_review_id:
        ids_csv = [token.strip() for token in (review.github_review_id or "").split(",") if token.strip()]
        for idx, gh_id in enumerate(ids_csv):
            if gh_id == github_comment_id and idx < len(comments):
                comment = comments[idx]
                if isinstance(comment, dict):
                    return idx, comment.get("category"), comment.get("severity")

    if inline_path is not None:
        for idx, comment in enumerate(comments):
            if not isinstance(comment, dict):
                continue
            if comment.get("file_path") != inline_path:
                continue
            if inline_line is not None and comment.get("line_number") != inline_line:
                continue
            return idx, comment.get("category"), comment.get("severity")

    return None, None, None


async def record_feedback(
    session: AsyncSession,
    parsed: ParsedFeedback,
) -> ReviewFeedback | None:
    """Persist a parsed feedback event. Returns the row, or None if no review match."""
    review = await _find_target_review(session, parsed=parsed)
    if review is None:
        logger.info(
            "Feedback ignored — no matching review (repo=%s pr=%s action=%s)",
            parsed.repo_full_name,
            parsed.pr_number,
            parsed.action,
        )
        return None

    comment_index, category, severity = _locate_comment_index(
        review,
        github_comment_id=parsed.github_comment_id,
        inline_path=parsed.inline_path,
        inline_line=parsed.inline_line,
    )

    payload = {
        "review_id": review.id,
        "repo_id": review.repo_id,
        "comment_index": comment_index,
        "github_comment_id": parsed.github_comment_id,
        "github_review_id": parsed.github_review_id,
        "action": parsed.action,
        "category": category,
        "severity": severity,
        "github_user": parsed.github_user,
        "reply_body": parsed.reply_body,
    }

    stmt = pg_insert(ReviewFeedback).values(payload)
    stmt = stmt.on_conflict_do_nothing(constraint="uq_review_feedback_event")
    await session.execute(stmt)
    await session.flush()

    # Re-fetch the row so the caller can inspect it.
    fetched = await session.execute(
        select(ReviewFeedback).where(
            ReviewFeedback.review_id == review.id,
            ReviewFeedback.action == parsed.action,
            ReviewFeedback.github_comment_id == parsed.github_comment_id,
        ).limit(1)
    )
    return fetched.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Stats (consumed by the dashboard)
# ---------------------------------------------------------------------------


def _agreement_rate(positive: int, negative: int) -> float:
    """positive / (positive + negative); 0 when both are zero."""
    total = positive + negative
    return positive / total if total > 0 else 0.0


def compute_overall_agreement(rows: Iterable[ReviewFeedback]) -> dict[str, float | int]:
    """Aggregate counts + agreement rate for a flat row list."""
    counts: Counter[str] = Counter()
    for row in rows:
        counts[row.action] += 1
    positive = sum(counts[a] for a in POSITIVE_ACTIONS)
    negative = sum(counts[a] for a in NEGATIVE_ACTIONS)
    return {
        "total_events": int(sum(counts.values())),
        "resolved": counts[ACTION_RESOLVED],
        "dismissed": counts[ACTION_DISMISSED],
        "replied": counts[ACTION_REPLIED],
        "thumbs_up": counts[ACTION_THUMBS_UP],
        "thumbs_down": counts[ACTION_THUMBS_DOWN],
        "agreement_rate": _agreement_rate(positive, negative),
    }


def compute_category_agreement(rows: Iterable[ReviewFeedback]) -> list[dict[str, Any]]:
    """Per-category agreement breakdown."""
    by_cat: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        if row.category:
            by_cat[row.category][row.action] += 1
    out: list[dict[str, Any]] = []
    for cat, counts in by_cat.items():
        positive = sum(counts[a] for a in POSITIVE_ACTIONS)
        negative = sum(counts[a] for a in NEGATIVE_ACTIONS)
        out.append({
            "category": cat,
            "resolved": counts[ACTION_RESOLVED],
            "dismissed": counts[ACTION_DISMISSED],
            "replied": counts[ACTION_REPLIED],
            "agreement_rate": _agreement_rate(positive, negative),
            "total": int(sum(counts.values())),
        })
    out.sort(key=lambda r: r["total"], reverse=True)
    return out


def compute_daily_agreement(
    rows: Iterable[ReviewFeedback],
    *,
    days: int,
    end: datetime | None = None,
) -> list[dict[str, Any]]:
    """Per-day agreement-rate timeseries for a chart."""
    end = end or utc_now_naive()
    start = end - timedelta(days=days)
    buckets: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        if row.created_at is None or row.created_at < start:
            continue
        day = row.created_at.date().isoformat()
        buckets[day][row.action] += 1

    series: list[dict[str, Any]] = []
    for day_offset in range(days, -1, -1):
        day = (end - timedelta(days=day_offset)).date().isoformat()
        counts = buckets.get(day, Counter())
        positive = sum(counts[a] for a in POSITIVE_ACTIONS)
        negative = sum(counts[a] for a in NEGATIVE_ACTIONS)
        series.append({
            "date": day,
            "resolved": counts[ACTION_RESOLVED],
            "dismissed": counts[ACTION_DISMISSED],
            "replied": counts[ACTION_REPLIED],
            "agreement_rate": _agreement_rate(positive, negative),
        })
    return series


async def fetch_feedback_rows(
    session: AsyncSession,
    *,
    repo_id: str | None = None,
    since: datetime | None = None,
    limit: int | None = None,
) -> Sequence[ReviewFeedback]:
    """Pull feedback rows with optional filters."""
    stmt = select(ReviewFeedback).order_by(desc(ReviewFeedback.created_at))
    if repo_id is not None:
        try:
            import uuid as _uuid

            stmt = stmt.where(ReviewFeedback.repo_id == _uuid.UUID(repo_id))
        except ValueError:
            return []
    if since is not None:
        stmt = stmt.where(ReviewFeedback.created_at >= since)
    if limit is not None:
        stmt = stmt.limit(limit)
    result = await session.execute(stmt)
    return result.scalars().all()


async def count_feedback_actions(
    session: AsyncSession,
    *,
    repo_id: str | None = None,
) -> dict[str, int]:
    """Cheap aggregate count by action — used by the health summary widget."""
    stmt = select(ReviewFeedback.action, func.count())
    if repo_id is not None:
        try:
            import uuid as _uuid

            stmt = stmt.where(ReviewFeedback.repo_id == _uuid.UUID(repo_id))
        except ValueError:
            return {}
    stmt = stmt.group_by(ReviewFeedback.action)
    result = await session.execute(stmt)
    return {row[0]: int(row[1]) for row in result.all()}
