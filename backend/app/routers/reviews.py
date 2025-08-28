"""Review endpoints — paginated list, detail, filters by repo/severity/category."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import desc, select

from app.config import settings
from app.core.database import async_session
from app.core.rate_limit import limiter
from app.models.database import Repo, Review
from app.services.orchestrator import ReviewOrchestrator

router = APIRouter()
_orchestrator = ReviewOrchestrator()

# Defensive cap on diff size for the public preview endpoint. The body-size
# middleware already gates the entire request, but a conservative per-field
# limit keeps the cost-guard pre-check cheap.
_MAX_PREVIEW_DIFF_CHARS = 1_000_000

_SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def _highest_severity(comments: list | None) -> str | None:
    best: str | None = None
    for item in comments or []:
        if not isinstance(item, dict):
            continue
        sev = item.get("severity")
        if not isinstance(sev, str) or sev not in _SEVERITY_RANK:
            continue
        if best is None or _SEVERITY_RANK[sev] < _SEVERITY_RANK[best]:
            best = sev
    return best


class PreviewReviewRequest(BaseModel):
    """Run the review pipeline on a raw unified diff (no GitHub required)."""

    repo_id: str = Field(default="local-preview", min_length=1, max_length=256)
    pr_number: int = Field(default=0, ge=0)
    pr_title: str = Field(default="", max_length=500)
    diff: str = Field(
        ...,
        min_length=1,
        max_length=_MAX_PREVIEW_DIFF_CHARS,
        description="Full unified diff text (max 1 MB)",
    )


@router.post("/preview")
@limiter.limit(settings.rate_limit_preview)
async def preview_review(request: Request, body: PreviewReviewRequest):
    """
    End-to-end review: parse diff → cost guard → LLM (or mock if no API keys).

    Returns the structured ``ReviewOutput`` plus per-run telemetry so the
    dashboard's review-preview page can show tokens, latency, and hashes
    without a second lookup. Set ``LLM_MOCK_MODE=true`` or omit API keys to
    get deterministic stub output in CI.
    """
    result, reason = await _orchestrator.review_pr(
        body.repo_id,
        body.pr_number,
        body.diff,
        body.pr_title,
    )
    if result is None:
        raise HTTPException(status_code=400, detail={"error": reason or "review failed"})
    return {
        **result.output.model_dump(),
        "diff_hash": result.diff_hash,
        "prompt_hash": result.prompt_hash,
        "model_version": result.model_version,
        "total_tokens": result.total_tokens,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "latency_ms": result.latency_ms,
        "retrieval_ms": result.retrieval_ms,
        "pipeline_step_timings": result.pipeline_step_timings,
        "pr_title": body.pr_title,
    }


@router.get("/")
async def list_reviews(
    repo_id: str | None = None,
    status: str | None = None,
    category: str | None = None,
    severity: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    """List reviews with pagination and filters."""
    async with async_session() as session:
        stmt = (
            select(Review, Repo.full_name)
            .join(Repo, Review.repo_id == Repo.id)
            .order_by(desc(Review.created_at))
        )

        if repo_id:
            try:
                stmt = stmt.where(Review.repo_id == UUID(repo_id))
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="Invalid repo_id UUID") from exc
        if status:
            stmt = stmt.where(Review.status == status)
        if start_date:
            stmt = stmt.where(Review.created_at >= start_date)
        if end_date:
            stmt = stmt.where(Review.created_at <= end_date)

        rows = (await session.execute(stmt)).all()

    def _matches_comment_filters(review: Review) -> bool:
        if not category and not severity:
            return True
        comments = review.comments or []
        for item in comments:
            if not isinstance(item, dict):
                continue
            category_ok = not category or item.get("category") == category
            severity_ok = not severity or item.get("severity") == severity
            if category_ok and severity_ok:
                return True
        return False

    filtered = [(r, name) for r, name in rows if _matches_comment_filters(r)]
    total = len(filtered)
    start = (page - 1) * per_page
    page_rows = filtered[start : start + per_page]

    payload = [
        {
            "id": str(review.id),
            "repo_id": str(review.repo_id),
            "repo_name": repo_name,
            "pr_number": review.pr_number,
            "pr_title": review.pr_title,
            "status": review.status,
            "comment_count": len(review.comments or []),
            "highest_severity": _highest_severity(review.comments),
            "quality_score": review.pr_quality_score,
            "created_at": review.created_at.isoformat() if review.created_at else None,
        }
        for review, repo_name in page_rows
    ]
    return {"reviews": payload, "total": total, "page": page, "per_page": per_page}


@router.get("/{review_id}")
async def get_review(review_id: str):
    """Single review with all comments, severity badges, line anchors."""
    try:
        review_uuid = UUID(review_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid review_id UUID") from exc

    async with async_session() as session:
        stmt = (
            select(Review, Repo.full_name)
            .join(Repo, Review.repo_id == Repo.id)
            .where(Review.id == review_uuid)
        )
        row = (await session.execute(stmt)).one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail="Review not found")
        review, repo_name = row

    return {
        "review": {
            "id": str(review.id),
            "repo_id": str(review.repo_id),
            "repo_name": repo_name,
            "pr_number": review.pr_number,
            "pr_title": review.pr_title,
            "pr_url": review.pr_url,
            "diff_hash": review.diff_hash,
            "prompt_hash": review.prompt_hash,
            "model_version": review.model_version,
            "status": review.status,
            "summary": review.summary,
            "pr_quality_score": review.pr_quality_score,
            "review_focus_areas": review.review_focus_areas or [],
            "triage_result": review.triage_result,
            "pipeline_step_timings": review.pipeline_step_timings,
            "comments": review.comments or [],
            "total_tokens": review.total_tokens,
            "input_tokens": review.input_tokens,
            "output_tokens": review.output_tokens,
            "latency_ms": review.latency_ms,
            "retrieval_ms": review.retrieval_ms,
            "created_at": review.created_at.isoformat() if review.created_at else None,
        }
    }
