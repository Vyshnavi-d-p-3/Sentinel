"""Integration tests for /api/v1/repos — need Postgres (same as other integration tests)."""

from __future__ import annotations

import random
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, text

from app.core.database import async_session
from app.main import app
from app.models.database import Repo


@pytest.mark.asyncio
async def test_repos_list_get_patch() -> None:
    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
    except Exception as e:
        pytest.skip(f"Database not reachable: {e}")

    rid = uuid.uuid4()
    # github_id is UNIQUE; avoid collisions in repeated runs.
    gh_id = random.randint(1_000_000_000_000, 9_000_000_000_000)

    async with async_session() as session:
        session.add(
            Repo(
                id=rid,
                github_id=gh_id,
                full_name="sentinel/test-repo",
                installation_id=42,
                default_branch="main",
                auto_review=True,
                daily_token_budget=1000,
                per_pr_token_cap=500,
            )
        )
        await session.commit()

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r = await ac.get("/api/v1/repos/")
            assert r.status_code == 200, r.text
            data = r.json()
            assert any(x["id"] == str(rid) for x in data["repos"])

            r2 = await ac.get(f"/api/v1/repos/{rid}")
            assert r2.status_code == 200
            assert r2.json()["full_name"] == "sentinel/test-repo"

            r3 = await ac.patch(
                f"/api/v1/repos/{rid}/settings",
                json={"auto_review": False, "daily_token_budget": 2000},
            )
            assert r3.status_code == 200, r3.text
            assert r3.json()["auto_review"] is False
            assert r3.json()["daily_token_budget"] == 2000

            r4 = await ac.patch(
                "/api/v1/repos/00000000-0000-0000-0000-000000000001/settings",
                json={"auto_review": True},
            )
            assert r4.status_code == 404
    finally:
        async with async_session() as session:
            await session.execute(delete(Repo).where(Repo.id == rid))
            await session.commit()
