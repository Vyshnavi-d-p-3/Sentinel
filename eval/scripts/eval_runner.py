"""
Eval runner — load fixture PRs, run the review pipeline, score predictions
against hand-labeled ground truth, and (optionally) gate against a baseline.

Usage:

    # Run, write the full results JSON, and write a baseline if missing.
    python eval/scripts/eval_runner.py \
        --fixtures eval/fixtures/ \
        --output eval/results.json \
        --baseline eval/baselines/baseline.json

    # In CI: fail (exit 2) if any strict-mode category F1 drops > threshold.
    python eval/scripts/eval_runner.py \
        --fixtures eval/fixtures/ \
        --baseline eval/baselines/baseline.json \
        --threshold 0.05 \
        --gate

The runner forces ``LLM_MOCK_MODE=true`` by default so it works in CI without
provider credentials. Override with ``--no-mock`` for real-LLM eval runs.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
EVAL_DIR = REPO_ROOT / "eval"
SCRIPTS_DIR = EVAL_DIR / "scripts"
BACKEND_DIR = REPO_ROOT / "backend"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from scoring import (  # noqa: E402  (sys.path manipulation above)
    DualEvalResult,
    EvalComment,
    EvalScorer,
    comments_from_payload,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("eval_runner")

EXIT_OK = 0
EXIT_NO_FIXTURES = 1
EXIT_REGRESSION = 2
EXIT_PIPELINE_ERROR = 3


@dataclass
class Fixture:
    """One labeled PR ready to run through the pipeline."""

    pr_id: str
    repo: str
    pr_number: int
    pr_title: str
    diff: str
    expected_comments: list[EvalComment]
    is_clean_pr: bool
    expected_no_comments: list[EvalComment]


def load_fixtures(fixture_dir: Path) -> list[Fixture]:
    """Load and normalize fixture JSON files."""
    fixtures: list[Fixture] = []
    files = sorted(fixture_dir.glob("*.json"))
    for path in files:
        try:
            payload = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            logger.error("Skipping %s: invalid JSON (%s)", path.name, exc)
            continue

        diff = payload.get("diff") or ""
        if not diff:
            logger.warning("Skipping %s: no diff", path.name)
            continue

        expected = comments_from_payload(payload.get("expected_comments", []))
        not_expected = comments_from_payload(payload.get("expected_no_comments", []))
        is_clean = bool(payload.get("is_clean") or payload.get("clean_pr")) or (
            len(expected) == 0 and len(not_expected) == 0 and bool(payload.get("expected_clean", False))
        )

        fixtures.append(
            Fixture(
                pr_id=str(payload.get("pr_id") or path.stem),
                repo=str(payload.get("repo") or "unknown/unknown"),
                pr_number=int(payload.get("pr_number") or 0),
                pr_title=str(payload.get("pr_title") or ""),
                diff=diff,
                expected_comments=expected,
                is_clean_pr=is_clean,
                expected_no_comments=not_expected,
            )
        )

    logger.info("Loaded %d fixtures from %s", len(fixtures), fixture_dir)
    return fixtures


def _ensure_mock_mode(force_mock: bool) -> None:
    """LLM mock mode lets eval runs succeed without provider credentials."""
    if force_mock:
        os.environ["LLM_MOCK_MODE"] = "true"


async def _run_one_fixture(orchestrator: Any, fixture: Fixture) -> tuple[list[EvalComment], dict[str, Any]]:
    """Run a single fixture and return (predicted comments, run metadata)."""
    # Distinct ``repo_id`` per fixture so token budgets do not stack on one
    # synthetic "eval-harness" ID during large batched eval runs.
    result, reason = await orchestrator.review_pr(
        repo_id=f"eval:{fixture.pr_id}",
        pr_number=fixture.pr_number,
        raw_diff=fixture.diff,
        pr_title=fixture.pr_title,
    )

    if result is None or result.output is None:
        logger.warning("Fixture %s skipped: %s", fixture.pr_id, reason)
        return [], {"skipped": True, "reason": reason or "unknown"}

    # ``mode="json"`` so enums become plain strings (matches ``comments_from_payload``).
    comments_payload = [c.model_dump(mode="json") for c in result.output.comments]
    metadata = {
        "skipped": False,
        "diff_hash": result.diff_hash,
        "prompt_hash": result.prompt_hash,
        "model_version": result.model_version,
        "total_tokens": result.total_tokens,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "latency_ms": result.latency_ms,
        "pr_quality_score": result.output.pr_quality_score,
    }
    return comments_from_payload(comments_payload), metadata


async def run_pipeline(fixtures: list[Fixture]) -> tuple[
    list[list[EvalComment]],
    list[list[EvalComment]],
    list[bool],
    list[dict[str, Any]],
]:
    """Run all fixtures and collect predictions, ground truth, and per-PR metadata."""
    from app.services.orchestrator import ReviewOrchestrator

    orchestrator = ReviewOrchestrator()

    predictions: list[list[EvalComment]] = []
    ground_truths: list[list[EvalComment]] = []
    clean_flags: list[bool] = []
    per_pr_metadata: list[dict[str, Any]] = []

    for fixture in fixtures:
        try:
            preds, meta = await _run_one_fixture(orchestrator, fixture)
        except Exception as exc:
            logger.exception("Fixture %s crashed pipeline: %s", fixture.pr_id, exc)
            preds, meta = [], {"skipped": True, "reason": f"crash: {exc}"}

        predictions.append(preds)
        ground_truths.append(fixture.expected_comments)
        clean_flags.append(fixture.is_clean_pr)
        per_pr_metadata.append({"pr_id": fixture.pr_id, **meta})

    return predictions, ground_truths, clean_flags, per_pr_metadata


async def _persist_run_to_db(dual, *, metadata: list[dict[str, Any]], args: argparse.Namespace) -> None:
    """
    Insert a row into ``eval_runs`` summarizing the current run so the dashboard's
    **Eval → run history** table shows it. Imports the backend lazily because the
    runner must still work in environments where SQLAlchemy isn't installed.
    """
    from app.core.database import async_session  # noqa: E402
    from app.models.database import EvalRun, Prompt  # noqa: E402
    from app.prompts.review_prompts import review_prompt_template_hash  # noqa: E402
    from app.services.pricing import estimate_llm_cost_usd  # noqa: E402
    from sqlalchemy import select  # noqa: E402

    # Pull prompt/model metadata from the first completed PR — every PR in a run
    # uses the same orchestrator so these are identical across the dataset.
    completed = [m for m in metadata if isinstance(m, dict) and not m.get("skipped")]
    prompt_hash = (completed[0].get("prompt_hash") if completed else None) or review_prompt_template_hash()
    model_version = (completed[0].get("model_version") if completed else None) or (
        "mock" if os.environ.get("LLM_MOCK_MODE") == "true" else "claude-sonnet-4-20250514"
    )

    latencies = [m["latency_ms"] for m in completed if isinstance(m.get("latency_ms"), (int, float))]
    avg_latency_ms = (sum(latencies) / len(latencies)) if latencies else None
    total_cost_usd = sum(
        estimate_llm_cost_usd(
            model_version,
            int(m.get("input_tokens", 0) or 0),
            int(m.get("output_tokens", 0) or 0),
        )
        for m in completed
    ) or None

    strict = dual.strict
    soft = dual.soft

    def _cat(cat_set, name: str) -> tuple[float | None, float | None, float | None]:
        m = cat_set.per_category.get(name)
        if m is None:
            return None, None, None
        return m.precision, m.recall, m.f1

    sec_p, sec_r, sec_f = _cat(strict, "security")
    bug_p, bug_r, bug_f = _cat(strict, "bug")
    perf_p, perf_r, perf_f = _cat(strict, "performance")
    style_p, style_r, style_f = _cat(strict, "style")

    async with async_session() as session:
        # Ensure the foreign key is satisfiable — seed a minimal Prompt row if missing.
        existing = (
            await session.execute(select(Prompt).where(Prompt.hash == prompt_hash))
        ).scalar_one_or_none()
        if existing is None:
            session.add(
                Prompt(
                    hash=prompt_hash,
                    name="sentinel_review_pipeline",
                    version=1,
                    system_prompt="(bundled in app/prompts/review_prompts.py)",
                    user_template="(assembled per-step — see review_prompts.py)",
                    description="Auto-registered by eval_runner --persist-db",
                    is_active=False,
                )
            )
            await session.flush()

        session.add(
            EvalRun(
                prompt_hash=prompt_hash,
                model_version=model_version,
                dataset_version=args.dataset_version,
                security_precision=sec_p, security_recall=sec_r, security_f1=sec_f,
                bug_precision=bug_p, bug_recall=bug_r, bug_f1=bug_f,
                perf_precision=perf_p, perf_recall=perf_r, perf_f1=perf_f,
                style_precision=style_p, style_recall=style_r, style_f1=style_f,
                overall_precision=strict.overall_precision,
                overall_recall=strict.overall_recall,
                overall_f1=strict.overall_f1,
                total_prs_evaluated=len(metadata),
                avg_latency_ms=avg_latency_ms,
                total_cost_usd=total_cost_usd,
                git_commit_sha=os.environ.get("GITHUB_SHA"),
                ci_run_url=(
                    f"{os.environ['GITHUB_SERVER_URL']}/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['GITHUB_RUN_ID']}"
                    if all(k in os.environ for k in ("GITHUB_SERVER_URL", "GITHUB_REPOSITORY", "GITHUB_RUN_ID"))
                    else None
                ),
                notes=args.notes,
            )
        )
        await session.commit()
        logger.info(
            "Persisted EvalRun — prompt=%s strict_overall_f1=%.3f soft_overall_f1=%.3f",
            prompt_hash[:7], strict.overall_f1, soft.overall_f1,
        )


def check_regression(
    current: DualEvalResult,
    baseline_path: Path,
    threshold: float,
    save_if_missing: bool,
) -> bool:
    """
    Compare current strict per-category F1 against the stored baseline.

    Returns True iff every category's F1 stayed within ``threshold`` of baseline.
    Writes a fresh baseline (and returns True) if none exists and
    ``save_if_missing`` is set.
    """
    if not baseline_path.exists():
        if save_if_missing:
            baseline_path.parent.mkdir(parents=True, exist_ok=True)
            baseline_path.write_text(json.dumps(current.summary(), indent=2))
            logger.info("No baseline found — wrote new baseline to %s", baseline_path)
            return True
        logger.error("Baseline %s missing and --no-save-baseline set", baseline_path)
        return False

    baseline = json.loads(baseline_path.read_text())
    baseline_strict = baseline.get("strict", baseline)  # tolerate either layout
    baseline_per_cat = baseline_strict.get("per_category", {})

    passed = True
    for cat, metrics in current.strict.per_category.items():
        baseline_f1 = float(baseline_per_cat.get(cat, {}).get("f1", 0.0))
        delta = baseline_f1 - metrics.f1
        if delta > threshold:
            logger.error(
                "REGRESSION: %s strict F1 dropped %.3f (baseline=%.3f, current=%.3f)",
                cat,
                delta,
                baseline_f1,
                metrics.f1,
            )
            passed = False
        else:
            logger.info(
                "%s strict F1=%.3f (baseline=%.3f, delta=%+.3f)",
                cat,
                metrics.f1,
                baseline_f1,
                -delta,
            )
    return passed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Sentinel evaluation harness")
    parser.add_argument("--fixtures", type=Path, default=EVAL_DIR / "fixtures")
    parser.add_argument("--baseline", type=Path, default=EVAL_DIR / "baselines" / "baseline.json")
    parser.add_argument("--output", type=Path, default=None, help="Write full results JSON")
    parser.add_argument("--threshold", type=float, default=0.05, help="Max allowed F1 drop per category")
    parser.add_argument("--gate", action="store_true", help="Exit non-zero on regression (CI mode)")
    parser.add_argument("--no-save-baseline", action="store_true", help="Do not auto-create a missing baseline")
    parser.add_argument("--no-mock", action="store_true", help="Use real LLM providers instead of mock mode")
    parser.add_argument(
        "--persist-db",
        action="store_true",
        help="Write an EvalRun row to the backend database so the dashboard history fills up.",
    )
    parser.add_argument(
        "--dataset-version",
        type=str,
        default="fixtures-v1",
        help="Label for this fixture set (recorded on the EvalRun row).",
    )
    parser.add_argument(
        "--notes",
        type=str,
        default=None,
        help="Free-form notes recorded on the EvalRun row.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    _ensure_mock_mode(force_mock=not args.no_mock)

    fixtures = load_fixtures(args.fixtures)
    if not fixtures:
        logger.error("No fixtures found in %s", args.fixtures)
        return EXIT_NO_FIXTURES

    try:
        predictions, ground_truths, clean_flags, metadata = asyncio.run(run_pipeline(fixtures))
    except Exception as exc:
        logger.exception("Pipeline run failed: %s", exc)
        return EXIT_PIPELINE_ERROR

    scorer = EvalScorer(line_tolerance=5)
    dual = scorer.score_dataset_dual(predictions, ground_truths, clean_pr_flags=clean_flags)

    summary = dual.summary()
    summary["per_pr"] = metadata
    logger.info(
        "Strict overall F1=%.3f | Soft overall F1=%.3f | Clean-PR FP rate=%.2f%%",
        dual.strict.overall_f1,
        dual.soft.overall_f1,
        dual.clean_pr.clean_pr_fp_rate * 100,
    )

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(summary, indent=2))
        logger.info("Wrote results to %s", args.output)

    if args.persist_db:
        try:
            asyncio.run(_persist_run_to_db(dual, metadata=metadata, args=args))
        except Exception as exc:  # noqa: BLE001 — best-effort side effect
            logger.warning("Skipped DB persistence (%s)", exc)

    passed = check_regression(
        dual,
        baseline_path=args.baseline,
        threshold=args.threshold,
        save_if_missing=not args.no_save_baseline,
    )

    if args.gate and not passed:
        return EXIT_REGRESSION
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
