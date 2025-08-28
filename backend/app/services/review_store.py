"""Persist reviews and cost ledger rows after the pipeline runs."""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from typing import Any

from sqlalchemy import delete, select

from app.models.database import CostLedger, Repo, Review
from app.models.review_output import ReviewOutput
from app.services.orchestrator_types import PipelineStepUsage


async def get_or_create_repo(
    session,
    *,
    github_id: int,
    full_name: str,
    installation_id: int,
) -> Repo:
    result = await session.execute(select(Repo).where(Repo.github_id == github_id))
    repo = result.scalar_one_or_none()
    if repo:
        if repo.full_name != full_name or repo.installation_id != installation_id:
            repo.full_name = full_name
            repo.installation_id = installation_id
        return repo

    repo = Repo(
        github_id=github_id,
        full_name=full_name,
        installation_id=installation_id,
    )
    session.add(repo)
    await session.flush()
    return repo


async def upsert_review(
    session,
    *,
    repo_id: uuid.UUID,
    pr_number: int,
    pr_title: str | None,
    pr_url: str | None,
    diff_hash: str,
    prompt_hash: str,
    model_version: str,
    status: str,
    summary: str | None,
    comments: list[dict[str, Any]],
    pr_quality_score: float | None,
    review_focus_areas: list[str] | None,
    triage_result: dict[str, Any] | None,
    pipeline_step_timings: dict[str, Any] | None,
    total_tokens: int,
    input_tokens: int,
    output_tokens: int,
    latency_ms: int,
    retrieval_ms: int | None = None,
) -> Review:
    result = await session.execute(
        select(Review).where(
            Review.repo_id == repo_id,
            Review.pr_number == pr_number,
            Review.diff_hash == diff_hash,
        )
    )
    existing = result.scalar_one_or_none()
    focus = review_focus_areas or []
    if existing:
        existing.pr_title = pr_title
        existing.pr_url = pr_url
        existing.prompt_hash = prompt_hash
        existing.model_version = model_version
        existing.status = status
        existing.summary = summary
        existing.comments = comments
        existing.pr_quality_score = pr_quality_score
        existing.review_focus_areas = focus
        existing.triage_result = triage_result
        existing.pipeline_step_timings = pipeline_step_timings
        existing.total_tokens = total_tokens
        existing.input_tokens = input_tokens
        existing.output_tokens = output_tokens
        existing.latency_ms = latency_ms
        existing.retrieval_ms = retrieval_ms
        await session.flush()
        return existing

    review = Review(
        repo_id=repo_id,
        pr_number=pr_number,
        pr_title=pr_title,
        pr_url=pr_url,
        diff_hash=diff_hash,
        prompt_hash=prompt_hash,
        model_version=model_version,
        status=status,
        summary=summary,
        comments=comments,
        pr_quality_score=pr_quality_score,
        review_focus_areas=focus,
        triage_result=triage_result,
        pipeline_step_timings=pipeline_step_timings,
        total_tokens=total_tokens,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        retrieval_ms=retrieval_ms,
    )
    session.add(review)
    await session.flush()
    return review


async def append_cost_ledger(
    session,
    *,
    repo_id: uuid.UUID,
    review_id: uuid.UUID | None,
    model_version: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
    pipeline_step: str = "review",
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> None:
    row = CostLedger(
        repo_id=repo_id,
        review_id=review_id,
        model_version=model_version,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cache_read_tokens,
        cache_write_tokens=cache_write_tokens,
        cost_usd=cost_usd,
        pipeline_step=pipeline_step,
    )
    session.add(row)


def review_output_to_comment_dicts(output: ReviewOutput) -> list[dict[str, Any]]:
    return [c.model_dump(mode="json") for c in output.comments]


async def persist_completed_review(
    session,
    *,
    repo: Repo,
    pr_number: int,
    pr_title: str | None,
    pr_url: str | None,
    diff_hash: str,
    prompt_hash: str,
    model_version: str,
    output: ReviewOutput,
    latency_ms: int,
    total_tokens: int,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
    triage_result: dict[str, Any] | None = None,
    pipeline_step_timings: dict[str, Any] | None = None,
    step_usages: Iterable[PipelineStepUsage] | None = None,
    retrieval_ms: int | None = None,
) -> Review:
    """
    Persist a completed review and (idempotently) replace its cost-ledger rows.

    If ``step_usages`` is provided, one ``cost_ledger`` row is written per
    pipeline step (triage / review / crossref / synthesis). Otherwise a single
    aggregate ``review`` row is written using the totals.
    """
    review = await upsert_review(
        session,
        repo_id=repo.id,
        pr_number=pr_number,
        pr_title=pr_title,
        pr_url=pr_url,
        diff_hash=diff_hash,
        prompt_hash=prompt_hash,
        model_version=model_version,
        status="completed",
        summary=output.summary,
        comments=review_output_to_comment_dicts(output),
        pr_quality_score=output.pr_quality_score,
        review_focus_areas=output.review_focus_areas,
        triage_result=triage_result,
        pipeline_step_timings=pipeline_step_timings,
        total_tokens=total_tokens,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        retrieval_ms=retrieval_ms,
    )
    # Idempotency: a webhook retry must not double-count tokens for this review.
    await session.execute(delete(CostLedger).where(CostLedger.review_id == review.id))

    if step_usages:
        for usage in step_usages:
            await append_cost_ledger(
                session,
                repo_id=repo.id,
                review_id=review.id,
                model_version=usage.model_version,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                cost_usd=usage.cost_usd,
                pipeline_step=usage.step,
                cache_read_tokens=usage.cache_read_tokens,
                cache_write_tokens=usage.cache_write_tokens,
            )
    else:
        await append_cost_ledger(
            session,
            repo_id=repo.id,
            review_id=review.id,
            model_version=model_version,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            pipeline_step="review",
        )
    return review


async def persist_skipped_review(
    session,
    *,
    repo: Repo,
    pr_number: int,
    pr_title: str | None,
    pr_url: str | None,
    diff_hash: str,
    prompt_hash: str,
    model_version: str,
    reason: str,
    latency_ms: int = 0,
) -> Review:
    return await upsert_review(
        session,
        repo_id=repo.id,
        pr_number=pr_number,
        pr_title=pr_title,
        pr_url=pr_url,
        diff_hash=diff_hash,
        prompt_hash=prompt_hash,
        model_version=model_version,
        status="skipped",
        summary=reason,
        comments=[],
        pr_quality_score=None,
        review_focus_areas=[],
        triage_result=None,
        pipeline_step_timings=None,
        total_tokens=0,
        input_tokens=0,
        output_tokens=0,
        latency_ms=latency_ms,
        retrieval_ms=None,
    )


async def set_review_github_artifacts(
    session,
    *,
    review: Review,
    github_review_id: str | None,
    check_run_id: str | None,
) -> None:
    """Attach GitHub API artifact IDs to a persisted review."""
    review.github_review_id = github_review_id
    review.check_run_id = check_run_id
    await session.flush()
