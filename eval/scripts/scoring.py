"""
Evaluation scoring engine — per-category P/R/F1 with dual-level matching,
clean-PR false positive rate, and confidence calibration buckets.

Matching modes:
- strict: file_path exact AND line_number within ±tolerance AND category exact
- soft:   file_path exact AND category exact (line ignored)

Both modes are reported per-category and overall, plus aggregate metrics that
the spec calls out (clean-PR FP rate and confidence calibration).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


CATEGORIES: tuple[str, ...] = ("security", "bug", "performance", "style", "suggestion")


@dataclass
class EvalComment:
    """A comment from either prediction or ground truth."""

    file_path: str
    line_number: int
    category: str
    severity: str = ""
    description: str = ""
    confidence: float = 0.0


@dataclass
class CategoryMetrics:
    """Precision, recall, F1 for a single category."""

    category: str
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0

    @property
    def precision(self) -> float:
        denom = self.true_positives + self.false_positives
        return self.true_positives / denom if denom > 0 else 0.0

    @property
    def recall(self) -> float:
        denom = self.true_positives + self.false_negatives
        return self.true_positives / denom if denom > 0 else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) > 0 else 0.0

    def to_dict(self) -> dict[str, float | int]:
        return {
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
        }


@dataclass
class EvalResult:
    """Single-mode evaluation result across all categories."""

    per_category: dict[str, CategoryMetrics] = field(default_factory=dict)
    total_prs: int = 0

    def _sum(self, attr: str) -> int:
        return sum(getattr(m, attr) for m in self.per_category.values())

    @property
    def overall_precision(self) -> float:
        tp = self._sum("true_positives")
        fp = self._sum("false_positives")
        return tp / (tp + fp) if (tp + fp) > 0 else 0.0

    @property
    def overall_recall(self) -> float:
        tp = self._sum("true_positives")
        fn = self._sum("false_negatives")
        return tp / (tp + fn) if (tp + fn) > 0 else 0.0

    @property
    def overall_f1(self) -> float:
        p, r = self.overall_precision, self.overall_recall
        return 2 * p * r / (p + r) if (p + r) > 0 else 0.0

    def summary(self) -> dict:
        return {
            "overall": {
                "precision": self.overall_precision,
                "recall": self.overall_recall,
                "f1": self.overall_f1,
            },
            "per_category": {cat: m.to_dict() for cat, m in self.per_category.items()},
            "total_prs": self.total_prs,
        }


@dataclass
class CleanPRMetrics:
    """False-positive behavior on intentionally clean PRs."""

    total_clean_prs: int = 0
    clean_prs_with_any_comment: int = 0
    total_false_positive_comments: int = 0

    @property
    def clean_pr_fp_rate(self) -> float:
        if self.total_clean_prs == 0:
            return 0.0
        return self.clean_prs_with_any_comment / self.total_clean_prs

    def to_dict(self) -> dict[str, float | int]:
        return {
            "total_clean_prs": self.total_clean_prs,
            "clean_prs_with_any_comment": self.clean_prs_with_any_comment,
            "total_false_positive_comments": self.total_false_positive_comments,
            "clean_pr_fp_rate": self.clean_pr_fp_rate,
        }


@dataclass
class CalibrationBucket:
    """Confidence-calibration bucket: predicted confidence vs realized accuracy."""

    bucket_lo: float
    bucket_hi: float
    total: int = 0
    true_positives: int = 0

    @property
    def accuracy(self) -> float:
        return self.true_positives / self.total if self.total > 0 else 0.0

    def to_dict(self) -> dict[str, float | int]:
        return {
            "bucket_lo": self.bucket_lo,
            "bucket_hi": self.bucket_hi,
            "total": self.total,
            "true_positives": self.true_positives,
            "accuracy": self.accuracy,
        }


@dataclass
class DualEvalResult:
    """Strict + soft results, plus clean-PR FP and calibration."""

    strict: EvalResult
    soft: EvalResult
    clean_pr: CleanPRMetrics
    calibration: list[CalibrationBucket]
    total_prs: int

    def summary(self) -> dict:
        return {
            "strict": self.strict.summary(),
            "soft": self.soft.summary(),
            "clean_pr": self.clean_pr.to_dict(),
            "confidence_calibration": [b.to_dict() for b in self.calibration],
            "total_prs": self.total_prs,
        }


def _new_category_dict() -> dict[str, CategoryMetrics]:
    return {cat: CategoryMetrics(category=cat) for cat in CATEGORIES}


def _empty_calibration_buckets() -> list[CalibrationBucket]:
    return [CalibrationBucket(bucket_lo=i / 10, bucket_hi=(i + 1) / 10) for i in range(10)]


class EvalScorer:
    """
    Score predicted review comments against hand-labeled ground truth.

    Backward compatible with the original `score_dataset` (strict-only).
    Use `score_dataset_dual` for the spec's dual-level evaluation plus
    clean-PR FP rate and calibration buckets.
    """

    CATEGORIES = list(CATEGORIES)

    def __init__(self, line_tolerance: int = 5):
        # The +/-5 line tolerance was empirically determined. +/-3 was too strict
        # (penalized legitimate findings on neighboring lines), +/-10 was too
        # loose (gave credit for wrong-file-same-category matches).
        self.line_tolerance = line_tolerance

    def score_dataset(
        self,
        all_predictions: list[list[EvalComment]],
        all_ground_truths: list[list[EvalComment]],
    ) -> EvalResult:
        """Strict-mode scoring (kept for backward compatibility)."""
        result = EvalResult(per_category=_new_category_dict(), total_prs=len(all_predictions))
        for preds, truths in zip(all_predictions, all_ground_truths):
            self._score_single_pr(preds, truths, result, mode="strict")
        return result

    def score_dataset_dual(
        self,
        all_predictions: list[list[EvalComment]],
        all_ground_truths: list[list[EvalComment]],
        clean_pr_flags: list[bool] | None = None,
    ) -> DualEvalResult:
        """
        Score in both strict and soft modes simultaneously.

        ``clean_pr_flags`` marks PRs that intentionally have no real issues so
        we can compute the spec's clean-PR FP rate. If omitted, a PR is treated
        as clean iff its ground-truth comment list is empty.
        """
        strict = EvalResult(per_category=_new_category_dict(), total_prs=len(all_predictions))
        soft = EvalResult(per_category=_new_category_dict(), total_prs=len(all_predictions))
        calibration = _empty_calibration_buckets()
        clean_pr = CleanPRMetrics()

        if clean_pr_flags is None:
            clean_pr_flags = [len(t) == 0 for t in all_ground_truths]

        for preds, truths, is_clean in zip(all_predictions, all_ground_truths, clean_pr_flags):
            strict_match_results = self._score_single_pr(preds, truths, strict, mode="strict")
            self._score_single_pr(preds, truths, soft, mode="soft")
            self._update_calibration(preds, strict_match_results, calibration)

            if is_clean:
                clean_pr.total_clean_prs += 1
                if preds:
                    clean_pr.clean_prs_with_any_comment += 1
                    clean_pr.total_false_positive_comments += len(preds)

        return DualEvalResult(
            strict=strict,
            soft=soft,
            clean_pr=clean_pr,
            calibration=calibration,
            total_prs=len(all_predictions),
        )

    def _score_single_pr(
        self,
        predictions: list[EvalComment],
        ground_truth: list[EvalComment],
        result: EvalResult,
        mode: str,
    ) -> list[bool]:
        """
        Match predictions to ground truth in the requested mode.

        Returns a per-prediction list of booleans (true if it matched a truth)
        so the caller can attribute correctness for confidence calibration.
        """
        matched_truths: set[int] = set()
        per_pred_matched: list[bool] = []

        for pred in predictions:
            cat = pred.category
            if cat not in result.per_category:
                per_pred_matched.append(False)
                continue

            matched_index: int | None = None
            for i, truth in enumerate(ground_truth):
                if i in matched_truths:
                    continue
                if self._is_match(pred, truth, mode=mode):
                    matched_index = i
                    break

            if matched_index is not None:
                result.per_category[cat].true_positives += 1
                matched_truths.add(matched_index)
                per_pred_matched.append(True)
            else:
                result.per_category[cat].false_positives += 1
                per_pred_matched.append(False)

        for i, truth in enumerate(ground_truth):
            if i not in matched_truths:
                cat = truth.category
                if cat in result.per_category:
                    result.per_category[cat].false_negatives += 1

        return per_pred_matched

    def _update_calibration(
        self,
        predictions: list[EvalComment],
        per_pred_matched: list[bool],
        calibration: list[CalibrationBucket],
    ) -> None:
        for pred, matched in zip(predictions, per_pred_matched):
            confidence = max(0.0, min(1.0, float(pred.confidence)))
            bucket_idx = min(int(confidence * 10), len(calibration) - 1)
            bucket = calibration[bucket_idx]
            bucket.total += 1
            if matched:
                bucket.true_positives += 1

    def _is_match(self, predicted: EvalComment, truth: EvalComment, *, mode: str = "strict") -> bool:
        if predicted.file_path != truth.file_path:
            return False
        if predicted.category != truth.category:
            return False
        if mode == "strict":
            if abs(predicted.line_number - truth.line_number) > self.line_tolerance:
                return False
        return True


def comments_from_payload(items: Iterable[dict]) -> list[EvalComment]:
    """Build EvalComment list from JSON payload (fixtures or pipeline output)."""
    out: list[EvalComment] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        file_path = str(item.get("file_path") or item.get("file") or "")
        line_value = item.get("line_number") if "line_number" in item else item.get("line", 0)
        try:
            line_number = int(line_value)
        except (TypeError, ValueError):
            line_number = 0
        category = str(item.get("category") or "").lower()
        severity = str(item.get("severity") or "")
        description = str(item.get("description") or item.get("body") or "")
        confidence = float(item.get("confidence") or 0.0)
        if not file_path or not category:
            continue
        out.append(
            EvalComment(
                file_path=file_path,
                line_number=line_number,
                category=category,
                severity=severity,
                description=description,
                confidence=confidence,
            )
        )
    return out
