"""
Consistency checker for Sentinel eval fixtures.

Validates that every fixture conforms to the labeling rubric (schema,
allowed enums, required fields) and reports category/severity distribution
so we can keep the dataset balanced.

Usage:

    python eval/scripts/consistency_check.py --fixtures eval/fixtures/

Exit codes:
    0 — all fixtures valid
    1 — schema or enum violations found
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

ALLOWED_CATEGORIES = {"security", "bug", "performance", "style", "suggestion"}
ALLOWED_SEVERITIES = {"critical", "high", "medium", "low"}
REQUIRED_TOP_LEVEL_KEYS = {"pr_id", "repo", "pr_number", "pr_title", "diff", "expected_comments"}
REQUIRED_COMMENT_KEYS = {"file", "line", "category"}


@dataclass
class CheckReport:
    fixtures_seen: int = 0
    valid_fixtures: int = 0
    errors: list[str] = field(default_factory=list)
    category_counts: Counter[str] = field(default_factory=Counter)
    severity_counts: Counter[str] = field(default_factory=Counter)
    clean_pr_count: int = 0
    total_labeled_comments: int = 0


def _validate_comment(comment: dict, source: str, idx: int, errors: list[str]) -> bool:
    if not isinstance(comment, dict):
        errors.append(f"{source}: expected_comments[{idx}] is not an object")
        return False

    missing = REQUIRED_COMMENT_KEYS - comment.keys()
    if missing:
        errors.append(f"{source}: expected_comments[{idx}] missing keys: {sorted(missing)}")
        return False

    category = str(comment.get("category", "")).lower()
    if category not in ALLOWED_CATEGORIES:
        errors.append(
            f"{source}: expected_comments[{idx}] has invalid category={category!r} "
            f"(allowed: {sorted(ALLOWED_CATEGORIES)})"
        )
        return False

    severity = str(comment.get("severity", "")).lower()
    if severity and severity not in ALLOWED_SEVERITIES:
        errors.append(
            f"{source}: expected_comments[{idx}] has invalid severity={severity!r} "
            f"(allowed: {sorted(ALLOWED_SEVERITIES)})"
        )
        return False

    line = comment.get("line")
    if not isinstance(line, int) or line <= 0:
        errors.append(f"{source}: expected_comments[{idx}] line must be a positive int")
        return False

    file_path = comment.get("file")
    if not isinstance(file_path, str) or not file_path.strip():
        errors.append(f"{source}: expected_comments[{idx}] missing/empty file path")
        return False

    return True


def check_fixture(path: Path, report: CheckReport) -> None:
    report.fixtures_seen += 1
    source = path.name

    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        report.errors.append(f"{source}: invalid JSON ({exc})")
        return

    missing = REQUIRED_TOP_LEVEL_KEYS - payload.keys()
    if missing:
        report.errors.append(f"{source}: missing top-level keys {sorted(missing)}")
        return

    if not isinstance(payload.get("diff"), str) or not payload["diff"].strip():
        report.errors.append(f"{source}: diff must be a non-empty string")
        return

    expected = payload.get("expected_comments") or []
    if not isinstance(expected, list):
        report.errors.append(f"{source}: expected_comments must be a list")
        return

    is_clean = bool(payload.get("is_clean", False) or payload.get("clean_pr", False))
    if is_clean:
        report.clean_pr_count += 1
        if expected:
            report.errors.append(
                f"{source}: is_clean/clean_pr=true but expected_comments is non-empty"
            )
            return

    fixture_ok = True
    for i, comment in enumerate(expected):
        if not _validate_comment(comment, source, i, report.errors):
            fixture_ok = False
            continue
        report.category_counts[str(comment.get("category")).lower()] += 1
        sev = str(comment.get("severity") or "").lower()
        if sev:
            report.severity_counts[sev] += 1

    report.total_labeled_comments += len(expected)

    # Validate the optional context_files block consumed by the ablation harness.
    if "context_files" in payload:
        ctx = payload["context_files"]
        if not isinstance(ctx, dict):
            report.errors.append(f"{source}: context_files must be an object (file_path -> [chunks])")
            fixture_ok = False
        else:
            for fpath, chunks in ctx.items():
                if not isinstance(fpath, str) or not fpath:
                    report.errors.append(f"{source}: context_files key must be a non-empty file path")
                    fixture_ok = False
                    continue
                if not isinstance(chunks, list) or not all(isinstance(c, str) for c in chunks):
                    report.errors.append(
                        f"{source}: context_files[{fpath!r}] must be a list of strings"
                    )
                    fixture_ok = False

    if fixture_ok:
        report.valid_fixtures += 1


def print_report(report: CheckReport) -> None:
    print(f"Fixtures seen:     {report.fixtures_seen}")
    print(f"Fixtures valid:    {report.valid_fixtures}")
    print(f"Clean PRs:         {report.clean_pr_count}")
    print(f"Total labels:      {report.total_labeled_comments}")
    if report.category_counts:
        total = sum(report.category_counts.values())
        print("\nCategory distribution:")
        for cat in sorted(ALLOWED_CATEGORIES):
            count = report.category_counts.get(cat, 0)
            pct = 100.0 * count / total if total else 0.0
            print(f"  {cat:<11s} {count:4d}  ({pct:5.1f}%)")
    if report.severity_counts:
        total = sum(report.severity_counts.values())
        print("\nSeverity distribution:")
        for sev in ("critical", "high", "medium", "low"):
            count = report.severity_counts.get(sev, 0)
            pct = 100.0 * count / total if total else 0.0
            print(f"  {sev:<8s} {count:4d}  ({pct:5.1f}%)")
    if report.errors:
        print(f"\n{len(report.errors)} error(s):")
        for err in report.errors:
            print(f"  - {err}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Sentinel eval fixtures")
    parser.add_argument("--fixtures", type=Path, default=Path("eval/fixtures"))
    args = parser.parse_args()

    if not args.fixtures.exists():
        print(f"Fixture directory not found: {args.fixtures}", file=sys.stderr)
        return 1

    report = CheckReport()
    for path in sorted(args.fixtures.glob("*.json")):
        check_fixture(path, report)

    print_report(report)
    return 0 if not report.errors else 1


if __name__ == "__main__":
    sys.exit(main())
