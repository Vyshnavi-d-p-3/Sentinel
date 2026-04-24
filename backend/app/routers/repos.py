"""Repository registry — list installations and update per-repo budgets / toggles.

Matches the project document: ``GET /api/v1/repos`` and
``PATCH /api/v1/repos/{id}/settings`` for token budgets, default branch, and
``auto_review``.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select

from app.core.database import async_session
from app.models.database import Repo

router = APIRouter()


class RepoOut(BaseModel):
    id: str
    github_id: int
    full_name: str
    installation_id: int
    default_branch: str
    auto_review: bool
    daily_token_budget: int
    per_pr_token_cap: int
    created_at: str | None
    updated_at: str | None


def _row_to_out(r: Repo) -> RepoOut:
    return RepoOut(
        id=str(r.id),
        github_id=int(r.github_id),
        full_name=str(r.full_name),
        installation_id=int(r.installation_id),
        default_branch=str(r.default_branch or "main"),
        auto_review=bool(r.auto_review),
        daily_token_budget=int(r.daily_token_budget or 0),
        per_pr_token_cap=int(r.per_pr_token_cap or 0),
        created_at=r.created_at.isoformat() if r.created_at else None,
        updated_at=r.updated_at.isoformat() if r.updated_at else None,
    )


class RepoListResponse(BaseModel):
    repos: list[RepoOut]
    total: int
    page: int
    per_page: int


class RepoSettingsBody(BaseModel):
    """All fields optional — only provided fields are updated."""

    default_branch: str | None = Field(default=None, min_length=1, max_length=256)
    auto_review: bool | None = None
    daily_token_budget: int | None = Field(default=None, ge=1, le=50_000_000)
    per_pr_token_cap: int | None = Field(default=None, ge=1, le=5_000_000)


@router.get("/", response_model=RepoListResponse)
async def list_repos(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
) -> RepoListResponse:
    """Paginated list of registered GitHub App installations (repos)."""
    offset = (page - 1) * per_page
    async with async_session() as session:
        count_q = select(func.count()).select_from(Repo)
        total = (await session.execute(count_q)).scalar() or 0
        q = select(Repo).order_by(desc(Repo.created_at)).offset(offset).limit(per_page)
        result = await session.execute(q)
        rows = list(result.scalars().all())

    return RepoListResponse(
        repos=[_row_to_out(r) for r in rows],
        total=int(total),
        page=page,
        per_page=per_page,
    )


@router.get("/{repo_id}", response_model=RepoOut)
async def get_repo(repo_id: UUID) -> RepoOut:
    """Single repository by id."""
    async with async_session() as session:
        r = await session.get(Repo, repo_id)
    if r is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    return _row_to_out(r)


@router.patch("/{repo_id}/settings", response_model=RepoOut)
async def patch_repo_settings(repo_id: UUID, body: RepoSettingsBody) -> RepoOut:
    """Update per-repo auto-review, budgets, or default branch label."""
    update_data = body.model_dump(exclude_unset=True)
    async with async_session() as session:
        r = await session.get(Repo, repo_id)
        if r is None:
            raise HTTPException(status_code=404, detail="Repository not found")
        if not update_data:
            return _row_to_out(r)
        if "default_branch" in update_data and update_data["default_branch"] is not None:
            r.default_branch = update_data["default_branch"]
        if "auto_review" in update_data and update_data["auto_review"] is not None:
            r.auto_review = bool(update_data["auto_review"])
        if "daily_token_budget" in update_data and update_data["daily_token_budget"] is not None:
            r.daily_token_budget = int(update_data["daily_token_budget"])
        if "per_pr_token_cap" in update_data and update_data["per_pr_token_cap"] is not None:
            r.per_pr_token_cap = int(update_data["per_pr_token_cap"])
        r.updated_at = datetime.utcnow()
        await session.commit()
        await session.refresh(r)
        return _row_to_out(r)
