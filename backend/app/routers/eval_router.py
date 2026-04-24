"""Eval endpoints — run history, per-category metrics, ablation deltas, prompt comparison.

The dashboard pulls this data to render the **Eval** page. Results come from two
sources, in priority order:

1. ``eval_runs`` DB table (populated when the eval runner is invoked with
   ``--persist-db`` or the optional HTTP trigger finishes — see below).
2. The JSON artifacts on disk at ``eval/results.json`` and
   ``eval/ablation_results.json`` (written by the GitHub Actions workflows and
   local ``eval_runner.py`` / ``ablation.py`` invocations).

Falling back to disk keeps the dashboard useful from day one without requiring
the runner to persist rows end-to-end.

**POST /trigger** (opt-in via ``EVAL_TRIGGER_ENABLED``) spawns
``eval/scripts/eval_runner.py`` in a controlled subprocess — see that handler for
the full security model.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import desc, select

from app.config import settings
from app.core.database import async_session
from app.core.rate_limit import limiter
from app.models.database import EvalRun

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

# ``backend/app/routers/eval_router.py`` → repo root = parents[3]
_REPO_ROOT = Path(__file__).resolve().parents[3]
_EVAL_DIR = Path(os.environ.get("SENTINEL_EVAL_DIR", _REPO_ROOT / "eval"))
_RESULTS_PATH = _EVAL_DIR / "results.json"
_ABLATION_PATH = _EVAL_DIR / "ablation_results.json"


def _resolved_under_repo(path: Path, repo_root: Path) -> Path:
    """Resolve ``path`` and ensure it stays inside ``repo_root`` (path traversal guard)."""
    root = repo_root.resolve()
    candidate = path.resolve()
    candidate.relative_to(root)
    return candidate


def _truncate_bytes(data: bytes, max_chars: int = 4000) -> str:
    text = data.decode(errors="replace")
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n… (truncated)"


# ---------------------------------------------------------------------------
# Response shapes
# ---------------------------------------------------------------------------


class CategoryMetric(BaseModel):
    precision: float
    recall: float
    f1: float
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0


class EvalRunSummary(BaseModel):
    """Compact card shown in the runs list."""

    id: str
    run_at: datetime | None = None
    prompt_hash: str | None = None
    model_version: str | None = None
    dataset_version: str | None = None
    overall_f1: float | None = None
    overall_precision: float | None = None
    overall_recall: float | None = None
    total_prs_evaluated: int = 0
    avg_latency_ms: float | None = None
    total_cost_usd: float | None = None
    git_commit_sha: str | None = None
    ci_run_url: str | None = None
    source: str = Field(description="'db' for persisted rows, 'disk' for artifact files.")


class EvalRunDetail(EvalRunSummary):
    """Full per-category + clean-PR metrics."""

    strict: dict[str, Any] = Field(default_factory=dict)
    soft: dict[str, Any] = Field(default_factory=dict)
    clean_pr: dict[str, Any] = Field(default_factory=dict)
    per_pr: list[dict[str, Any]] = Field(default_factory=list)
    notes: str | None = None


class EvalRunListResponse(BaseModel):
    runs: list[EvalRunSummary]
    sources: dict[str, bool] = Field(
        description="Which data sources were consulted and whether they had data."
    )


class AblationReport(BaseModel):
    fixtures_total: int = 0
    fixtures_with_context_files: int = 0
    no_context: dict[str, Any] = Field(default_factory=dict)
    with_context: dict[str, Any] = Field(default_factory=dict)
    delta: dict[str, float] = Field(default_factory=dict)
    per_pr: list[dict[str, Any]] = Field(default_factory=list)
    source: str


# ---------------------------------------------------------------------------
# DB → response helpers
# ---------------------------------------------------------------------------


def _db_row_to_summary(row: EvalRun) -> EvalRunSummary:
    return EvalRunSummary(
        id=str(row.id),
        run_at=row.run_at,
        prompt_hash=row.prompt_hash,
        model_version=row.model_version,
        dataset_version=row.dataset_version,
        overall_f1=row.overall_f1,
        overall_precision=row.overall_precision,
        overall_recall=row.overall_recall,
        total_prs_evaluated=int(row.total_prs_evaluated or 0),
        avg_latency_ms=row.avg_latency_ms,
        total_cost_usd=row.total_cost_usd,
        git_commit_sha=row.git_commit_sha,
        ci_run_url=row.ci_run_url,
        source="db",
    )


def _db_row_to_detail(row: EvalRun) -> EvalRunDetail:
    summary = _db_row_to_summary(row)
    per_cat_strict: dict[str, dict[str, float]] = {}
    for cat in ("security", "bug", "perf", "style"):
        p = getattr(row, f"{cat}_precision", None)
        r = getattr(row, f"{cat}_recall", None)
        f1 = getattr(row, f"{cat}_f1", None)
        if p is None and r is None and f1 is None:
            continue
        per_cat_strict[cat] = {"precision": p or 0.0, "recall": r or 0.0, "f1": f1 or 0.0}

    return EvalRunDetail(
        **summary.model_dump(),
        strict={
            "overall_precision": row.overall_precision or 0.0,
            "overall_recall": row.overall_recall or 0.0,
            "overall_f1": row.overall_f1 or 0.0,
            "per_category": per_cat_strict,
        },
        soft={},
        clean_pr={},
        per_pr=[],
        notes=row.notes,
    )


# ---------------------------------------------------------------------------
# Disk artifact helpers
# ---------------------------------------------------------------------------


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return None


def _overall_from_block(block: dict[str, Any]) -> dict[str, float | None]:
    """
    Both shapes are in the wild:
      - ``scoring.EvalResult.summary()`` writes ``{"overall": {precision, recall, f1}}``
      - DB rows write flat ``overall_f1`` / ``overall_precision`` / ``overall_recall``
    Normalize to a flat dict so callers don't have to care.
    """
    nested = block.get("overall") if isinstance(block.get("overall"), dict) else None
    return {
        "f1": (nested or {}).get("f1", block.get("overall_f1")),
        "precision": (nested or {}).get("precision", block.get("overall_precision")),
        "recall": (nested or {}).get("recall", block.get("overall_recall")),
    }


def _disk_results_summary(payload: dict[str, Any]) -> EvalRunSummary:
    strict_block = payload.get("strict", payload) or {}
    overall = _overall_from_block(strict_block)
    stat = path_to_stat(_RESULTS_PATH)
    return EvalRunSummary(
        id=f"disk:{stat or 'results'}",
        run_at=stat_to_datetime(_RESULTS_PATH),
        prompt_hash=payload.get("prompt_hash"),
        model_version=payload.get("model_version"),
        dataset_version=payload.get("dataset_version"),
        overall_f1=overall["f1"],
        overall_precision=overall["precision"],
        overall_recall=overall["recall"],
        total_prs_evaluated=int(strict_block.get("total_prs") or payload.get("total_prs") or 0),
        avg_latency_ms=payload.get("avg_latency_ms"),
        total_cost_usd=payload.get("total_cost_usd"),
        git_commit_sha=payload.get("git_commit_sha"),
        ci_run_url=payload.get("ci_run_url"),
        source="disk",
    )


def _flatten_block(block: dict[str, Any]) -> dict[str, Any]:
    """Return ``block`` with overall metrics also exposed as flat keys."""
    if not isinstance(block, dict):
        return {}
    flat = dict(block)
    overall = _overall_from_block(block)
    flat.setdefault("overall_f1", overall["f1"])
    flat.setdefault("overall_precision", overall["precision"])
    flat.setdefault("overall_recall", overall["recall"])
    return flat


def _disk_results_detail(payload: dict[str, Any]) -> EvalRunDetail:
    summary = _disk_results_summary(payload)
    return EvalRunDetail(
        **summary.model_dump(),
        strict=_flatten_block(payload.get("strict", {}) or {}),
        soft=_flatten_block(payload.get("soft", {}) or {}),
        clean_pr=payload.get("clean_pr", {}) or {},
        per_pr=payload.get("per_pr", []) or [],
        notes=payload.get("notes"),
    )


def path_to_stat(path: Path) -> str | None:
    try:
        return f"{path.stem}-{int(path.stat().st_mtime)}"
    except FileNotFoundError:
        return None


def stat_to_datetime(path: Path) -> datetime | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, UTC).replace(tzinfo=None)
    except FileNotFoundError:
        return None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/runs", response_model=EvalRunListResponse)
async def list_eval_runs(limit: int = Query(default=50, ge=1, le=500)):
    """Return recent eval runs from DB, augmented by the latest disk artifact."""
    db_runs: list[EvalRunSummary] = []
    async with async_session() as session:
        rows = (
            await session.execute(
                select(EvalRun).order_by(desc(EvalRun.run_at)).limit(limit)
            )
        ).scalars().all()
    db_runs.extend(_db_row_to_summary(r) for r in rows)

    sources = {"db": bool(db_runs), "disk": False}

    disk_payload = _load_json(_RESULTS_PATH)
    if disk_payload:
        sources["disk"] = True
        disk_summary = _disk_results_summary(disk_payload)
        # Only add the disk entry if it isn't already represented by a DB row with
        # the same prompt hash + commit sha (best-effort dedupe).
        dedup_key = (disk_summary.prompt_hash, disk_summary.git_commit_sha)
        if dedup_key != (None, None) and any(
            (r.prompt_hash, r.git_commit_sha) == dedup_key for r in db_runs
        ):
            pass
        else:
            db_runs.insert(0, disk_summary)

    return EvalRunListResponse(runs=db_runs, sources=sources)


@router.get("/runs/latest", response_model=EvalRunDetail)
async def get_latest_run():
    """
    Return the most useful single run to display by default on the dashboard:
    the newest DB row if present, otherwise the disk artifact.
    """
    async with async_session() as session:
        row = (
            await session.execute(select(EvalRun).order_by(desc(EvalRun.run_at)).limit(1))
        ).scalar_one_or_none()

    if row is not None:
        return _db_row_to_detail(row)

    payload = _load_json(_RESULTS_PATH)
    if payload is not None:
        return _disk_results_detail(payload)

    raise HTTPException(
        status_code=404,
        detail=(
            "No eval runs available. Run `python eval/scripts/eval_runner.py "
            "--output eval/results.json` or wait for the CI workflow to finish."
        ),
    )


@router.get("/runs/{run_id}", response_model=EvalRunDetail)
async def get_eval_run(run_id: str):
    if run_id.startswith("disk:"):
        payload = _load_json(_RESULTS_PATH)
        if payload is None:
            raise HTTPException(status_code=404, detail="Disk results artifact missing")
        return _disk_results_detail(payload)

    async with async_session() as session:
        row = (
            await session.execute(select(EvalRun).where(EvalRun.id == run_id))
        ).scalar_one_or_none()

    if row is None:
        raise HTTPException(status_code=404, detail=f"Eval run {run_id} not found")
    return _db_row_to_detail(row)


@router.get("/ablation", response_model=AblationReport)
async def get_ablation():
    """Return the most recent retrieval ablation report."""
    payload = _load_json(_ABLATION_PATH)
    if payload is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "No ablation report available. Run "
                "`python eval/scripts/ablation.py --output eval/ablation_results.json`."
            ),
        )
    return AblationReport(source="disk", **payload)


@router.get("/compare")
async def compare_prompts(
    prompt_a: str = Query(...),
    prompt_b: str = Query(...),
    limit: int = Query(default=10, ge=1, le=100),
):
    """
    Side-by-side comparison of two prompt versions across all categories.
    Picks the most recent run for each hash.
    """
    async with async_session() as session:
        def _latest(hash_: str):
            return (
                select(EvalRun)
                .where(EvalRun.prompt_hash == hash_)
                .order_by(desc(EvalRun.run_at))
                .limit(1)
            )

        a = (await session.execute(_latest(prompt_a))).scalar_one_or_none()
        b = (await session.execute(_latest(prompt_b))).scalar_one_or_none()

    if a is None or b is None:
        raise HTTPException(
            status_code=404,
            detail=f"Missing run for prompt(s): {'A ' if a is None else ''}{'B' if b is None else ''}",
        )

    return {
        "prompt_a": _db_row_to_detail(a).model_dump(),
        "prompt_b": _db_row_to_detail(b).model_dump(),
    }


async def _run_eval_runner_subprocess() -> tuple[int, bytes, bytes]:
    """
    Execute the pinned eval harness script via ``asyncio.create_subprocess_exec``.

    Security properties:

    - No shell — argv is a fixed list; only our repo-root script path is invoked.
    - Paths are resolved and constrained under the repository root.
    - Optional ``LLM_MOCK_MODE=true`` injection to avoid accidental cloud spend.
    """
    repo_root = _REPO_ROOT.resolve()
    runner_script = _resolved_under_repo(repo_root / "eval" / "scripts" / "eval_runner.py", repo_root)
    if not runner_script.is_file():
        raise HTTPException(
            status_code=500,
            detail={"error": "eval_runner_missing", "path": str(runner_script)},
        )

    fixtures_dir = _resolved_under_repo(_EVAL_DIR / "fixtures", repo_root)
    output_path = _resolved_under_repo(_RESULTS_PATH, repo_root)

    cmd: list[str] = [
        sys.executable,
        str(runner_script),
        "--fixtures",
        str(fixtures_dir),
        "--output",
        str(output_path),
    ]

    env = os.environ.copy()
    if settings.eval_trigger_force_mock:
        env["LLM_MOCK_MODE"] = "true"

    logger.info(
        "eval trigger: spawning runner cwd=%s timeout=%ss mock=%s",
        repo_root,
        settings.eval_trigger_timeout_sec,
        settings.eval_trigger_force_mock,
    )

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(repo_root),
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=settings.eval_trigger_timeout_sec,
        )
    except TimeoutError:
        proc.kill()
        await proc.wait()
        raise HTTPException(
            status_code=504,
            detail={
                "error": "eval_timeout",
                "timeout_sec": settings.eval_trigger_timeout_sec,
                "message": "Eval runner exceeded timeout — kill sent",
            },
        ) from None

    code = proc.returncode if proc.returncode is not None else 0
    return code, stdout, stderr


@router.post("/trigger")
@limiter.limit(settings.rate_limit_eval_trigger)
async def trigger_eval(request: Request):
    """
    Opt-in: run the offline eval harness (same entrypoint as CI).

    **Disabled by default** — set ``EVAL_TRIGGER_ENABLED=true`` after you understand
    the workload (fixtures × pipeline). Requires API key auth when configured.

    The subprocess uses mock LLM mode by default (``EVAL_TRIGGER_FORCE_MOCK``, on)
    so triggers cannot silently burn provider quota.
    """
    if not settings.eval_trigger_enabled:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "eval_trigger_disabled",
                "message": "Remote eval trigger is disabled on this deployment.",
                "hint": (
                    "Set EVAL_TRIGGER_ENABLED=true. Prefer enabling only behind "
                    "API_KEY auth and low rate limits."
                ),
            },
        )

    exit_code, stdout, stderr = await _run_eval_runner_subprocess()

    payload = _load_json(_RESULTS_PATH)
    stderr_tail = _truncate_bytes(stderr)
    stdout_tail = _truncate_bytes(stdout)

    if exit_code != 0 and payload is None:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "eval_runner_failed",
                "exit_code": exit_code,
                "stderr_tail": stderr_tail,
                "stdout_tail": stdout_tail,
            },
        )

    summary = _disk_results_summary(payload) if payload else None

    return {
        "status": "completed",
        "exit_code": exit_code,
        "regression_gate_failed": exit_code == 2,
        "forced_mock_llm": settings.eval_trigger_force_mock,
        "results_path": str(_RESULTS_PATH.resolve()),
        "summary": summary.model_dump() if summary else None,
        "stderr_tail": stderr_tail if exit_code != 0 else None,
    }
