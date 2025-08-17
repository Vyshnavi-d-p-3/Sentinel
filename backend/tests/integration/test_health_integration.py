"""Integration checks — require Postgres (GitHub Actions service container)."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.core.database import async_session
from app.main import app


@pytest.mark.asyncio
async def test_database_ping():
    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
    except Exception as e:
        pytest.skip(f"Database not reachable: {e}")


@pytest.mark.asyncio
async def test_health_reports_database():
    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
    except Exception as e:
        pytest.skip(f"Database not reachable: {e}")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["checks"]["database"] == "ok"
