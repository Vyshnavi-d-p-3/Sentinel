"""GitHub webhook handler — validates HMAC, routes PR events to orchestrator."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from typing import Any
from uuid import UUID

import httpx
from fastapi import APIRouter, Header, HTTPException, Request

from app.config import settings
from app.core.database import async_session
from app.core.idempotency import delivery_cache
from app.core.rate_limit import limiter
from app.core.security import verify_webhook_signature
from app.models.database import Repo
from app.prompts.review_prompts import review_prompt_template_hash
from app.retrieval.hybrid import HybridRetriever
from app.services.feedback_tracker import (
    parse_pull_request_review_comment_event,
    parse_pull_request_review_event,
    record_feedback,
)
from app.services.github_app_token import get_installation_access_token
from app.services.github_client import GithubClient
from app.services.orchestrator import ReviewOrchestrator
from app.services.pricing import estimate_llm_cost_usd
from app.services.review_store import (
    get_or_create_repo,
    persist_completed_review,
    persist_skipped_review,
    set_review_github_artifacts,
)

router = APIRouter()
logger = logging.getLogger(__name__)
# Live path: BM25/dense retrieval is wired against the real DB session factory.
_retriever = HybridRetriever(session_factory=async_session)
_orchestrator = ReviewOrchestrator(retriever=_retriever)


async def _fetch_diff(diff_url: str, token: str | None) -> str:
    headers = {
        "Accept": "application/vnd.github.v3.diff",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        resp = await client.get(diff_url, headers=headers)
        resp.raise_for_status()
    return resp.text


async def _run_review_from_payload(payload: dict[str, Any]) -> None:
    pr = payload.get("pull_request", {}) or {}
    repo_payload = payload.get("repository", {}) or {}
    installation = payload.get("installation") or {}

    pr_number = int(payload.get("number") or pr.get("number") or 0)
    if pr_number <= 0:
        logger.warning("Webhook payload missing valid PR number")
        return

    gh_repo_id = repo_payload.get("id")
    if gh_repo_id is None:
        logger.warning("Webhook payload missing repository id")
        return

    full_name = str(repo_payload.get("full_name") or "")
    installation_id = int(installation.get("id") or 0)
    pr_title = str(pr.get("title") or "")
    pr_url = pr.get("html_url")
    pr_url_s = str(pr_url) if pr_url else None
    diff_url = pr.get("diff_url")
    head = pr.get("head", {}) or {}
    head_sha = str(head.get("sha") or "")

    if not diff_url:
        logger.warning("PR #%s missing diff_url; skipping review", pr_number)
        return

    token = None
    if installation_id:
        token = await get_installation_access_token(installation_id)

    try:
        raw_diff = await _fetch_diff(str(diff_url), token)
    except Exception as exc:
        logger.exception("Failed to fetch diff for PR #%s: %s", pr_number, exc)
        return

    diff_hash = hashlib.sha256(raw_diff.encode()).hexdigest()
    prompt_hash = review_prompt_template_hash()

    repo_uuid: UUID | None = None
    async with async_session() as session:
        try:
            repo = await get_or_create_repo(
                session,
                github_id=int(gh_repo_id),
                full_name=full_name,
                installation_id=installation_id,
            )
            await session.commit()
            repo_uuid = repo.id
        except Exception:
            await session.rollback()
            logger.exception("Failed to upsert repo for PR #%s", pr_number)
            return

    if repo_uuid is None:
        return
    orch, reason = await _orchestrator.review_pr(
        repo_id=str(repo_uuid),
        pr_number=pr_number,
        raw_diff=raw_diff,
        pr_title=pr_title,
    )

    async with async_session() as session:
        try:
            repo = await session.get(Repo, repo_uuid)
            if repo is None:
                return
            if orch:
                cost_usd = sum(s.cost_usd for s in orch.step_usages) or estimate_llm_cost_usd(
                    orch.model_version,
                    orch.input_tokens,
                    orch.output_tokens,
                )
                review = await persist_completed_review(
                    session,
                    repo=repo,
                    pr_number=pr_number,
                    pr_title=pr_title or None,
                    pr_url=pr_url_s,
                    diff_hash=orch.diff_hash,
                    prompt_hash=orch.prompt_hash,
                    model_version=orch.model_version,
                    output=orch.output,
                    latency_ms=orch.latency_ms,
                    total_tokens=orch.total_tokens,
                    input_tokens=orch.input_tokens,
                    output_tokens=orch.output_tokens,
                    cost_usd=cost_usd,
                    triage_result=orch.triage_result,
                    pipeline_step_timings=orch.pipeline_step_timings,
                    step_usages=orch.step_usages,
                    retrieval_ms=orch.retrieval_ms,
                )
                if token and full_name and head_sha:
                    publisher = GithubClient(token)
                    publish = await publisher.publish_review(
                        repo_full_name=full_name,
                        pr_number=pr_number,
                        head_sha=head_sha,
                        summary=orch.output.summary,
                        comments=orch.output.comments,
                        quality_score=orch.output.pr_quality_score,
                    )
                    github_review_id = ",".join(str(cid) for cid in publish.comment_ids) or None
                    check_run_id = str(publish.check_run_id) if publish.check_run_id else None
                    await set_review_github_artifacts(
                        session,
                        review=review,
                        github_review_id=github_review_id,
                        check_run_id=check_run_id,
                    )
                logger.info(
                    "Review persisted for PR #%s (%s comments)",
                    pr_number,
                    len(orch.output.comments),
                )
            else:
                review = await persist_skipped_review(
                    session,
                    repo=repo,
                    pr_number=pr_number,
                    pr_title=pr_title or None,
                    pr_url=pr_url_s,
                    diff_hash=diff_hash,
                    prompt_hash=prompt_hash,
                    model_version=settings.default_model,
                    reason=reason or "skipped",
                )
                if token and full_name and head_sha:
                    publisher = GithubClient(token)
                    check_run_id = await publisher.create_check_run(
                        repo_full_name=full_name,
                        head_sha=head_sha,
                        summary=f"Sentinel skipped this review: {reason or 'skipped'}",
                        conclusion="neutral",
                        title="Sentinel Review Skipped",
                    )
                    await set_review_github_artifacts(
                        session,
                        review=review,
                        github_review_id=None,
                        check_run_id=str(check_run_id) if check_run_id else None,
                    )
                logger.warning("Review skipped for PR #%s: %s", pr_number, reason)
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception("Failed to persist review for PR #%s", pr_number)


_background_tasks: set[asyncio.Task[Any]] = set()


def _spawn_background(coro: Any) -> None:
    """Fire-and-forget a coroutine and retain a strong reference.

    We don't rely on ``fastapi.BackgroundTasks`` here because its parameter
    annotation doesn't survive the ``slowapi`` rate-limiter decorator
    (FastAPI's type-hint resolution uses ``__globals__`` of the wrapped
    function, which then misses symbols from this module). Using
    ``asyncio.create_task`` decouples webhook acknowledgement from the
    review pipeline and mirrors what a real queue worker would do.
    """
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


@router.post("/github")
@limiter.limit(settings.rate_limit_webhook)
async def github_webhook(
    request: Request,
    x_hub_signature_256: str = Header(...),
    x_github_event: str = Header(...),
    x_github_delivery: str | None = Header(default=None),
):
    """
    Receive, validate, and route GitHub webhook events.

    Security model:

    - Body must match ``X-Hub-Signature-256`` (HMAC-SHA256, constant-time compare).
    - Event header is constrained to a small allow-list — unknown events are
      ignored without doing further work.
    - ``X-GitHub-Delivery`` is used as an idempotency key so retried deliveries
      don't re-run the full pipeline.
    """
    payload = await request.body()

    # Reject empty bodies upfront — defends against accidental open-port pings.
    if not payload:
        raise HTTPException(status_code=400, detail="Empty webhook payload")

    if not verify_webhook_signature(payload, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    # Idempotency: if this delivery has been processed before, ack with 200 and
    # do nothing. We mark *after* the JSON parse succeeds so a malformed retry
    # doesn't poison the cache.
    if x_github_delivery and delivery_cache.has_seen(x_github_delivery):
        logger.info("Duplicate delivery %s — skipping", x_github_delivery)
        return {"status": "duplicate", "delivery": x_github_delivery}

    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from exc

    if x_github_delivery:
        delivery_cache.mark_seen(x_github_delivery)

    if x_github_event == "pull_request":
        action = body.get("action")
        if action in {"opened", "synchronize", "reopened"}:
            _spawn_background(_run_review_from_payload(body))
            return {"status": "accepted", "event": x_github_event, "action": action}
        return {"status": "ignored", "event": x_github_event, "action": action}

    if x_github_event in {"pull_request_review", "pull_request_review_comment"}:
        _spawn_background(_capture_feedback(x_github_event, body))
        return {"status": "accepted", "event": x_github_event, "action": body.get("action")}

    if x_github_event == "ping":
        # Standard GitHub App handshake event.
        return {"status": "pong", "zen": body.get("zen")}

    return {"status": "ignored", "event": x_github_event}


async def _capture_feedback(event: str, payload: dict[str, Any]) -> None:
    """Background-task entry point for feedback webhook events."""
    try:
        if event == "pull_request_review":
            parsed = parse_pull_request_review_event(payload)
        elif event == "pull_request_review_comment":
            parsed = parse_pull_request_review_comment_event(payload)
        else:
            return
        if parsed is None:
            return
        async with async_session() as session:
            try:
                await record_feedback(session, parsed)
                await session.commit()
            except Exception:
                await session.rollback()
                raise
    except Exception:
        logger.exception("Failed to capture feedback for event=%s", event)
