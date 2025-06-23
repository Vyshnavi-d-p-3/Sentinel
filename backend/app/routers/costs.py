"""Cost endpoints — daily breakdown, budget utilization, per-repo spend."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/summary")
async def cost_summary(repo_id: str | None = None, range: str = "7d"):
    return {"summary": {}}


@router.get("/daily")
async def daily_costs(repo_id: str | None = None):
    return {"daily": []}
