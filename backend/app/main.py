"""
Sentinel — AI-Powered Code Review with Reproducible Evaluation.
FastAPI application entry point.

Middleware order (outermost → innermost):
1. ``RequestIDMiddleware``       — assigns/propagates ``X-Request-ID``.
2. ``AccessLogMiddleware``       — structured access log per request.
3. ``SecurityHeadersMiddleware`` — adds XCTO, X-Frame-Options, COOP, etc.
4. ``BodySizeLimitMiddleware``   — rejects > 2 MiB bodies with HTTP 413.
5. ``CORSMiddleware``            — explicit allow-list, no wildcards.
6. ``SlowAPIMiddleware``         — per-IP rate limits (when slowapi installed).
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import settings, validate_settings_for_runtime
from app.core.auth import require_api_key
from app.core.database import Base, async_session, engine
from app.core.logging_config import configure_logging
from app.core.middleware import (
    AccessLogMiddleware,
    BodySizeLimitMiddleware,
    RequestIDMiddleware,
    SecurityHeadersMiddleware,
)
from app.core.rate_limit import (
    SLOWAPI_AVAILABLE,
    RateLimitExceeded,
    SlowAPIMiddleware,
    limiter,
)
from app.models import database as _models  # noqa: F401  (table registration)
from app.routers import (
    config_router,
    costs,
    eval_router,
    feedback,
    health,
    prompts,
    repos,
    reviews,
    tests,
    webhook,
)

configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: validate config, optionally auto-create tables. Shutdown: dispose pool."""
    config_warnings = validate_settings_for_runtime(settings)
    for w in config_warnings:
        logger.warning("config: %s", w)

    if settings.db_auto_create_tables:
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        except Exception:
            # First-pass create failed; most likely because the ``vector``
            # extension isn't installed on the local Postgres. Retry skipping
            # the ``repo_embeddings`` table so the rest of the API is usable
            # (reviews / prompts / costs all work without pgvector).
            logger.warning(
                "auto-create tables failed; retrying without repo_embeddings "
                "(install the pgvector extension to enable semantic retrieval)"
            )
            try:
                tables_without_vector = [
                    t for t in Base.metadata.sorted_tables if t.name != "repo_embeddings"
                ]
                async with engine.begin() as conn:
                    await conn.run_sync(
                        lambda sync_conn: Base.metadata.create_all(
                            sync_conn, tables=tables_without_vector
                        )
                    )
            except Exception:
                # We don't want a missing DB to prevent the API from booting in
                # demo / health-check scenarios — handlers still surface the
                # error via the /health probe.
                logger.exception("fallback auto-create tables failed; continuing")
    yield
    await engine.dispose()


app = FastAPI(
    title="Sentinel",
    description="AI-Powered Code Review with Reproducible Evaluation",
    version="0.1.0",
    lifespan=lifespan,
    # Hide the docs in production unless an operator explicitly wants them.
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
    openapi_url="/openapi.json" if settings.environment != "production" else None,
)


# ----- Middleware (registered in reverse — last added is outermost) -------
if SLOWAPI_AVAILABLE and SlowAPIMiddleware is not None:
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)

    @app.exception_handler(RateLimitExceeded)
    async def _rate_limit_handler(request: Request, exc: RateLimitExceeded):
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": "Rate limit exceeded", "limit": str(exc)},
        )


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-API-Key",
        "X-Request-ID",
        "X-Hub-Signature-256",
        "X-GitHub-Event",
        "X-GitHub-Delivery",
    ],
    expose_headers=["X-Request-ID"],
    max_age=600,
)
app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_request_body_bytes)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(AccessLogMiddleware)
app.add_middleware(RequestIDMiddleware)


# ----- Routers ------------------------------------------------------------
# Webhooks authenticate via HMAC, not API key, so they stay open here.
app.include_router(webhook.router, prefix="/webhook", tags=["webhooks"])

# Dashboard surface — protected by the API-key dependency when one is set.
api_protected = [Depends(require_api_key)]
app.include_router(reviews.router, prefix="/api/v1/reviews", tags=["reviews"], dependencies=api_protected)
app.include_router(repos.router, prefix="/api/v1/repos", tags=["repos"], dependencies=api_protected)
app.include_router(eval_router.router, prefix="/api/v1/eval", tags=["eval"], dependencies=api_protected)
app.include_router(costs.router, prefix="/api/v1/costs", tags=["costs"], dependencies=api_protected)
app.include_router(prompts.router, prefix="/api/v1/prompts", tags=["prompts"], dependencies=api_protected)
app.include_router(feedback.router, prefix="/api/v1/feedback", tags=["feedback"], dependencies=api_protected)
app.include_router(health.router, tags=["health-intelligence"], dependencies=api_protected)
app.include_router(config_router.router, prefix="/api/v1/config", tags=["config"], dependencies=api_protected)
app.include_router(tests.router, tags=["tests"], dependencies=api_protected)


# ----- Health / readiness / liveness --------------------------------------
@app.get("/health", tags=["health"])
async def health_check():
    """
    Combined liveness + dependency check used by the dashboard.

    Always returns HTTP 200 — the JSON body distinguishes ``healthy`` from
    ``degraded`` so the dashboard can render dependency status without the LB
    yanking traffic for, say, a missing embeddings table.
    """
    db_status = "ok"
    embeddings_status = "unknown"
    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
            exists = await session.execute(
                text("SELECT to_regclass('public.repo_embeddings')")
            )
            embeddings_status = "ready" if exists.scalar() else "missing"
    except Exception:
        db_status = "unavailable"
        embeddings_status = "unavailable"

    llm_live = bool(
        not settings.llm_mock_mode
        and (settings.anthropic_api_key.strip() or settings.openai_api_key.strip())
    )
    return {
        "status": "healthy" if db_status == "ok" else "degraded",
        "version": "0.1.0",
        "environment": settings.environment,
        "checks": {
            "database": db_status,
            "llm_gateway": "live" if llm_live else "mock",
            "embeddings_index": embeddings_status,
        },
    }


@app.get("/livez", tags=["health"], include_in_schema=False)
async def livez():
    """Liveness probe — never touches the database."""
    return {"status": "ok"}


@app.get("/readyz", tags=["health"], include_in_schema=False)
async def readyz():
    """Readiness probe — verifies DB connectivity. 503 if unavailable."""
    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unavailable"},
        )
    return {"status": "ready"}
