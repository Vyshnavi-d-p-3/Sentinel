"""
Eval runner — loads fixture PRs, runs the review pipeline, scores results.

Usage:
    python -m eval.scripts.eval_runner --fixtures eval/fixtures/ --output results.json

In CI:
    Compares against baseline and fails if any category F1 drops > 5%.
"""

import json
import sys
import argparse
import logging
from pathlib import Path

from scoring import EvalScorer, EvalComment, EvalResult

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_fixtures(fixture_dir: Path) -> list[dict]:
    """Load all JSON fixture files from directory."""
    fixtures = []
    for f in sorted(fixture_dir.glob("*.json")):
        with open(f) as fp:
            fixtures.append(json.load(fp))
    logger.info(f"Loaded {len(fixtures)} fixtures from {fixture_dir}")
    return fixtures


def check_regression(current: EvalResult, baseline_path: Path, threshold: float = 0.05) -> bool:
    """
    Compare current eval against baseline. Returns True if passed.
    Fails if any category F1 drops by more than threshold.
    """
    if not baseline_path.exists():
        logger.info("No baseline found — saving current as baseline")
        with open(baseline_path, "w") as f:
            json.dump(current.summary(), f, indent=2)
        return True

    with open(baseline_path) as f:
        baseline = json.load(f)

    passed = True
    for cat, metrics in current.per_category.items():
        baseline_f1 = baseline.get("per_category", {}).get(cat, {}).get("f1", 0.0)
        delta = baseline_f1 - metrics.f1
        if delta > threshold:
            logger.error(
                f"REGRESSION: {cat} F1 dropped {delta:.3f} "
                f"(baseline={baseline_f1:.3f}, current={metrics.f1:.3f})"
            )
            passed = False
        else:
            logger.info(f"{cat}: F1={metrics.f1:.3f} (baseline={baseline_f1:.3f}, delta={-delta:+.3f})")

    return passed


def main():
    parser = argparse.ArgumentParser(description="Run Sentinel evaluation")
    parser.add_argument("--fixtures", type=Path, default=Path("eval/fixtures"))
    parser.add_argument("--baseline", type=Path, default=Path("eval/baseline.json"))
    parser.add_argument("--threshold", type=float, default=0.05)
    args = parser.parse_args()

    fixtures = load_fixtures(args.fixtures)
    if not fixtures:
        logger.error("No fixtures found")
        sys.exit(1)

    # TODO: Run each fixture through the review pipeline
    # For now, exit cleanly
    logger.info("Eval runner scaffold — pipeline integration pending")


if __name__ == "__main__":
    main()
