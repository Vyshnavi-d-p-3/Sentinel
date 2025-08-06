"""
Sentinel — AI-Powered Code Review with Reproducible Evaluation.
FastAPI application entry point.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.database import engine
from app.routers import webhook, reviews, eval_router, costs, prompts


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(
    title="Sentinel",
    description="AI-Powered Code Review with Reproducible Evaluation",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhook.router, prefix="/webhook", tags=["webhooks"])
app.include_router(reviews.router, prefix="/api/v1/reviews", tags=["reviews"])
app.include_router(eval_router.router, prefix="/api/v1/eval", tags=["eval"])
app.include_router(costs.router, prefix="/api/v1/costs", tags=["costs"])
app.include_router(prompts.router, prefix="/api/v1/prompts", tags=["prompts"])


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "0.1.0",
        "checks": {"database": "ok", "llm_gateway": "ok", "embedding_index": "ok"},
    }
