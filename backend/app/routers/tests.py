"""Smart test generation endpoints."""

from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.models.review_output import ReviewComment
from app.services.orchestrator import ReviewOrchestrator
from app.services.test_generator import TestGenerator

router = APIRouter(prefix="/api/v1/tests")
_test_generator = TestGenerator()
_orchestrator = ReviewOrchestrator()


class TestGenRequest(BaseModel):
    """Request payload for Smart Test Generator."""

    pr_title: str = Field(default="", max_length=500)
    diff: str = Field(..., min_length=1)
    comments: list[ReviewComment] | None = None


class TestGenResponse(BaseModel):
    tests: list[dict]
    total_eligible: int
    total_generated: int
    skipped_reasons: list[str]
    tokens_used: int
    latency_ms: int
    model: str


def _split_diff_by_file(raw_diff: str) -> dict[str, str]:
    out: dict[str, str] = {}
    if not raw_diff.strip():
        return out
    parts = raw_diff.split("\ndiff --git ")
    for idx, part in enumerate(parts):
        piece = part if idx == 0 else "diff --git " + part
        piece = piece.strip()
        if not piece:
            continue
        first_line = piece.splitlines()[0]
        path = first_line.split(" b/", 1)[1].strip() if " b/" in first_line else "unknown"
        out[path] = piece
    return out


@router.post("/generate")
async def generate_tests(body: TestGenRequest) -> TestGenResponse:
    """Generate regression tests from provided or orchestrated review comments."""
    started = time.monotonic()
    comments = body.comments or []
    if not comments:
        review_result, reason = await _orchestrator.review_pr(
            repo_id="local-preview",
            pr_number=0,
            raw_diff=body.diff,
            pr_title=body.pr_title,
        )
        if review_result is None:
            raise HTTPException(status_code=400, detail={"error": reason or "review failed"})
        comments = review_result.output.comments

    file_diffs = _split_diff_by_file(body.diff)
    result = await _test_generator.generate(
        body.pr_title,
        comments,
        file_diffs,
    )
    tokens_used = result.usage.input_tokens + result.usage.output_tokens
    return TestGenResponse(
        tests=[t.model_dump(mode="json") for t in result.output.tests],
        total_eligible=result.output.total_comments_eligible,
        total_generated=result.output.total_tests_generated,
        skipped_reasons=result.output.skipped_reasons,
        tokens_used=tokens_used,
        latency_ms=int((time.monotonic() - started) * 1000),
        model=result.usage.model_version,
    )
