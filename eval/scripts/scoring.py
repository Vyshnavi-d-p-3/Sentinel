"""
Evaluation scoring engine — computes P/R/F1 per category with fuzzy matching.

Matching rules:
- file_path: exact match
- line_number: ±5 tolerance (line_tolerance)
- category: exact match

A predicted comment matches a ground-truth label if all three criteria are met.
"""

from dataclasses import dataclass, field


@dataclass
class EvalComment:
    """A comment from either prediction or ground truth."""
    file_path: str
    line_number: int
    category: str  # security, bug, performance, style
    severity: str = ""
    description: str = ""


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


@dataclass
class EvalResult:
    """Complete evaluation result across all categories."""
    per_category: dict[str, CategoryMetrics] = field(default_factory=dict)
    total_prs: int = 0

    @property
    def overall_precision(self) -> float:
        tp = sum(m.true_positives for m in self.per_category.values())
        fp = sum(m.false_positives for m in self.per_category.values())
        return tp / (tp + fp) if (tp + fp) > 0 else 0.0

    @property
    def overall_recall(self) -> float:
        tp = sum(m.true_positives for m in self.per_category.values())
        fn = sum(m.false_negatives for m in self.per_category.values())
        return tp / (tp + fn) if (tp + fn) > 0 else 0.0

    @property
    def overall_f1(self) -> float:
        p, r = self.overall_precision, self.overall_recall
        return 2 * p * r / (p + r) if (p + r) > 0 else 0.0

    def summary(self) -> dict:
        return {
            "overall": {"precision": self.overall_precision, "recall": self.overall_recall, "f1": self.overall_f1},
            "per_category": {
                cat: {"precision": m.precision, "recall": m.recall, "f1": m.f1}
                for cat, m in self.per_category.items()
            },
            "total_prs": self.total_prs,
        }


class EvalScorer:
    """
    Score predicted review comments against hand-labeled ground truth.

    Usage:
        scorer = EvalScorer(line_tolerance=5)
        result = scorer.score_dataset(predictions, ground_truths)
        print(result.summary())
    """

    CATEGORIES = ["security", "bug", "performance", "style"]

    def __init__(self, line_tolerance: int = 5):
        self.line_tolerance = line_tolerance

    def score_dataset(
        self,
        all_predictions: list[list[EvalComment]],
        all_ground_truths: list[list[EvalComment]],
    ) -> EvalResult:
        """Score predictions across all PRs. Each element is one PR's comments."""
        result = EvalResult(
            per_category={cat: CategoryMetrics(category=cat) for cat in self.CATEGORIES},
            total_prs=len(all_predictions),
        )

        for preds, truths in zip(all_predictions, all_ground_truths):
            self._score_single_pr(preds, truths, result)

        return result

    def _score_single_pr(
        self,
        predictions: list[EvalComment],
        ground_truth: list[EvalComment],
        result: EvalResult,
    ) -> None:
        """Score a single PR: match predictions to ground truth."""
        matched_truths: set[int] = set()

        for pred in predictions:
            cat = pred.category
            if cat not in result.per_category:
                continue

            matched = False
            for i, truth in enumerate(ground_truth):
                if i in matched_truths:
                    continue
                if self._is_match(pred, truth):
                    result.per_category[cat].true_positives += 1
                    matched_truths.add(i)
                    matched = True
                    break

            if not matched:
                result.per_category[cat].false_positives += 1

        # Unmatched ground truths are false negatives
        for i, truth in enumerate(ground_truth):
            if i not in matched_truths:
                cat = truth.category
                if cat in result.per_category:
                    result.per_category[cat].false_negatives += 1

    def _is_match(self, predicted: EvalComment, truth: EvalComment) -> bool:
        """Check if a prediction matches a ground truth label."""
        if predicted.file_path != truth.file_path:
            return False
        if predicted.category != truth.category:
            return False
        if abs(predicted.line_number - truth.line_number) > self.line_tolerance:
            return False
        return True
