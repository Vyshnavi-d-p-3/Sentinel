"""
Retrieval ablation harness — measures the F1 lift from supplying retrieval
context to the orchestrator's deep-review step.

For each fixture we run the pipeline twice:
  - Configuration "no_context"   — orchestrator constructed without a retriever
  - Configuration "with_context" — orchestrator constructed with a
    ``StaticContextRetriever`` populated from the fixture's ``context_files``
    field (when present)

We then score both configurations using the same dual-mode scorer the regular
eval runner uses and emit a comparison report::

    {
      "no_context":   {strict: ..., soft: ..., clean_pr: ...},
      "with_context": {strict: ..., soft: ..., clean_pr: ...},
      "delta": {
        "strict_overall_f1": +0.07,
        "soft_overall_f1":   +0.03,
        "per_category": {...}
      },
      "per_pr": [
        {"pr_id": "...", "no_context_comments": 2, "with_context_comments": 4,
         "context_chunks_supplied": 3, "retrieval_ms_avg": 0}
      ]
    }

When the LLM is in mock mode (the CI default) the deltas will be ~0; the script
is still useful as a smoke test for the retrieval wiring. Run ``--no-mock``
against a real provider to measure the actual lift.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
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

from scoring import (  # noqa: E402
    EvalComment,
    EvalScorer,
    comments_from_payload,
)
from static_retriever import StaticContextRetriever  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("ablation")

EXIT_OK = 0
EXIT_NO_FIXTURES = 1
EXIT_PIPELINE_ERROR = 3


# ---------------------------------------------------------------------------
# Fixture loading (variant-aware: uses context_files)
# ---------------------------------------------------------------------------


def load_fixtures(fixture_dir: Path) -> list[dict[str, Any]]:
    """Load fixture JSON, including the optional ``context_files`` map."""
    out: list[dict[str, Any]] = []
    for path in sorted(fixture_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            logger.error("Skipping %s: invalid JSON (%s)", path.name, exc)
            continue

        diff = payload.get("diff") or ""
        if not diff:
            logger.warning("Skipping %s: no diff", path.name)
            continue

        out.append({
            "pr_id": str(payload.get("pr_id") or path.stem),
            "repo": str(payload.get("repo") or "unknown/unknown"),
            "pr_number": int(payload.get("pr_number") or 0),
            "pr_title": str(payload.get("pr_title") or ""),
            "diff": diff,
            "expected_comments": comments_from_payload(payload.get("expected_comments", [])),
            "expected_no_comments": comments_from_payload(payload.get("expected_no_comments", [])),
            "is_clean_pr": (
                bool(payload.get("is_clean") or payload.get("clean_pr"))
                or (
                    not payload.get("expected_comments")
                    and not payload.get("expected_no_comments")
                    and bool(payload.get("expected_clean", False))
                )
            ),
            "context_files": dict(payload.get("context_files") or {}),
        })
    logger.info("Loaded %d fixtures from %s", len(out), fixture_dir)
    return out


# ---------------------------------------------------------------------------
# Pipeline driver
# ---------------------------------------------------------------------------


async def _run_one(orchestrator: Any, fx: dict[str, Any]) -> tuple[list[EvalComment], dict[str, Any]]:
    """Run a single fixture through the given orchestrator."""
    result, reason = await orchestrator.review_pr(
        repo_id=f"ablation-{fx['pr_id']}",
        pr_number=fx["pr_number"],
        raw_diff=fx["diff"],
        pr_title=fx["pr_title"],
    )
    if result is None or result.output is None:
        return [], {"skipped": True, "reason": reason or "unknown"}

    comments_payload = [c.model_dump() for c in result.output.comments]
    meta = {
        "skipped": False,
        "comment_count": len(comments_payload),
        "retrieval_ms": int(result.retrieval_ms or 0),
        "latency_ms": int(result.latency_ms or 0),
        "input_tokens": int(result.input_tokens or 0),
        "output_tokens": int(result.output_tokens or 0),
    }
    return comments_from_payload(comments_payload), meta


async def run_configuration(
    fixtures: list[dict[str, Any]],
    *,
    with_context: bool,
) -> tuple[list[list[EvalComment]], list[dict[str, Any]]]:
    """Run every fixture under one ablation configuration."""
    from app.services.orchestrator import ReviewOrchestrator  # local import keeps CLI fast

    predictions: list[list[EvalComment]] = []
    per_pr: list[dict[str, Any]] = []

    for fx in fixtures:
        retriever = (
            StaticContextRetriever(fx["context_files"]) if with_context and fx["context_files"] else None
        )
        orchestrator = ReviewOrchestrator(retriever=retriever)

        try:
            preds, meta = await _run_one(orchestrator, fx)
        except Exception as exc:
            logger.exception("Fixture %s crashed: %s", fx["pr_id"], exc)
            preds, meta = [], {"skipped": True, "reason": f"crash: {exc}"}

        predictions.append(preds)
        per_pr.append({
            "pr_id": fx["pr_id"],
            "context_chunks_supplied": (
                sum(len(v) for v in fx["context_files"].values()) if with_context else 0
            ),
            **meta,
        })

    return predictions, per_pr


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def _f1_lookup(scored_summary: dict[str, Any]) -> dict[str, float]:
    """Flatten the dual-summary into a per-category F1 dict for delta math."""
    strict = scored_summary.get("strict", {})
    per_cat = strict.get("per_category", {})
    out = {f"{cat}_strict_f1": float(metrics.get("f1", 0.0)) for cat, metrics in per_cat.items()}
    out["overall_strict_f1"] = float(strict.get("overall", {}).get("f1", 0.0))
    soft = scored_summary.get("soft", {})
    out["overall_soft_f1"] = float(soft.get("overall", {}).get("f1", 0.0))
    return out


def build_report(
    fixtures: list[dict[str, Any]],
    no_context_summary: dict[str, Any],
    with_context_summary: dict[str, Any],
    no_context_per_pr: list[dict[str, Any]],
    with_context_per_pr: list[dict[str, Any]],
) -> dict[str, Any]:
    no_flat = _f1_lookup(no_context_summary)
    with_flat = _f1_lookup(with_context_summary)

    delta = {
        key: round(with_flat.get(key, 0.0) - no_flat.get(key, 0.0), 4)
        for key in sorted(set(no_flat) | set(with_flat))
    }

    fixtures_with_context = sum(1 for fx in fixtures if fx["context_files"])

    per_pr_rows: list[dict[str, Any]] = []
    for fx, no_row, with_row in zip(fixtures, no_context_per_pr, with_context_per_pr):
        per_pr_rows.append({
            "pr_id": fx["pr_id"],
            "has_context_fixture": bool(fx["context_files"]),
            "no_context_comments": no_row.get("comment_count", 0),
            "with_context_comments": with_row.get("comment_count", 0),
            "context_chunks_supplied": with_row.get("context_chunks_supplied", 0),
            "retrieval_ms_with_context": with_row.get("retrieval_ms", 0),
        })

    return {
        "fixtures_total": len(fixtures),
        "fixtures_with_context_files": fixtures_with_context,
        "no_context": no_context_summary,
        "with_context": with_context_summary,
        "delta": delta,
        "per_pr": per_pr_rows,
    }


def print_human_summary(report: dict[str, Any]) -> None:
    delta = report.get("delta", {})
    print("=" * 60)
    print("RETRIEVAL ABLATION SUMMARY")
    print("=" * 60)
    print(f"Fixtures total:                  {report['fixtures_total']}")
    print(f"Fixtures with context_files:     {report['fixtures_with_context_files']}")
    print()
    print("Overall F1 deltas (with_context - no_context):")
    for key in ("overall_strict_f1", "overall_soft_f1"):
        sign = "+" if delta.get(key, 0.0) >= 0 else ""
        print(f"  {key:<22} {sign}{delta.get(key, 0.0):.4f}")
    print()
    print("Per-category strict F1 delta:")
    for key, value in delta.items():
        if not key.endswith("_strict_f1") or key == "overall_strict_f1":
            continue
        sign = "+" if value >= 0 else ""
        print(f"  {key:<26} {sign}{value:.4f}")
    print("=" * 60)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Retrieval ablation experiment")
    parser.add_argument("--fixtures", type=Path, default=EVAL_DIR / "fixtures")
    parser.add_argument(
        "--output",
        type=Path,
        default=EVAL_DIR / "ablation_results.json",
        help="Where to write the full ablation report",
    )
    parser.add_argument(
        "--no-mock",
        action="store_true",
        help="Use real LLM providers (deltas will only be meaningful here)",
    )
    parser.add_argument("--quiet", action="store_true", help="Skip the human-readable summary")
    return parser.parse_args()


def _ensure_mock_mode(force_mock: bool) -> None:
    if force_mock:
        os.environ["LLM_MOCK_MODE"] = "true"


async def _run_ablation(fixtures: list[dict[str, Any]]) -> dict[str, Any]:
    scorer = EvalScorer(line_tolerance=5)

    no_preds, no_meta = await run_configuration(fixtures, with_context=False)
    with_preds, with_meta = await run_configuration(fixtures, with_context=True)

    ground_truths = [fx["expected_comments"] for fx in fixtures]
    clean_flags = [fx["is_clean_pr"] for fx in fixtures]

    no_dual = scorer.score_dataset_dual(no_preds, ground_truths, clean_pr_flags=clean_flags)
    with_dual = scorer.score_dataset_dual(with_preds, ground_truths, clean_pr_flags=clean_flags)

    return build_report(
        fixtures,
        no_context_summary=no_dual.summary(),
        with_context_summary=with_dual.summary(),
        no_context_per_pr=no_meta,
        with_context_per_pr=with_meta,
    )


def main() -> int:
    args = parse_args()
    _ensure_mock_mode(force_mock=not args.no_mock)

    fixtures = load_fixtures(args.fixtures)
    if not fixtures:
        logger.error("No fixtures found in %s", args.fixtures)
        return EXIT_NO_FIXTURES

    try:
        report = asyncio.run(_run_ablation(fixtures))
    except Exception as exc:
        logger.exception("Ablation run failed: %s", exc)
        return EXIT_PIPELINE_ERROR

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2))
    logger.info("Wrote ablation report to %s", args.output)

    if not args.quiet:
        print_human_summary(report)

    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
