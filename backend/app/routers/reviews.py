"""Review endpoints — paginated list, detail, filters by repo/severity/category."""

from fastapi import APIRouter, Query

router = APIRouter()


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
