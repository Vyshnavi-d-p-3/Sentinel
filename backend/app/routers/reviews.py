"""Review endpoints — paginated list, detail, filters by repo/severity/category."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.orchestrator import ReviewOrchestrator

router = APIRouter()
_orchestrator = ReviewOrchestrator()


class PreviewReviewRequest(BaseModel):
    """Run the review pipeline on a raw unified diff (no GitHub required)."""

    repo_id: str = Field(default="local-preview", min_length=1, max_length=256)
    pr_number: int = Field(default=0, ge=0)
    pr_title: str = Field(default="", max_length=500)
    diff: str = Field(..., min_length=1, description="Full unified diff text")


@router.post("/preview")
async def preview_review(body: PreviewReviewRequest):
    """
    End-to-end review: parse diff → cost guard → LLM (or mock if no API keys).

    Set ``LLM_MOCK_MODE=true`` or omit API keys to get deterministic stub output in CI.
    """
    result, reason = await _orchestrator.review_pr(
        body.repo_id,
        body.pr_number,
        body.diff,
        body.pr_title,
    )
    if result is None:
        raise HTTPException(status_code=400, detail={"error": reason or "review failed"})
    return result


@router.get("/")
async def list_reviews(
    repo_id: str | None = None,
    status: str | None = None,
    category: str | None = None,
    severity: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    """List reviews with pagination and filters."""
    # TODO: query database
    return {"reviews": [], "total": 0, "page": page, "per_page": per_page}


@router.get("/{review_id}")
async def get_review(review_id: str):
    """Single review with all comments, severity badges, line anchors."""
    # TODO: fetch by ID
    return {"review": None}
