"""Tests for eval scoring engine — P/R/F1 computation with fuzzy matching."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "eval" / "scripts"))

from scoring import EvalScorer, EvalComment


def test_perfect_match():
    scorer = EvalScorer(line_tolerance=5)
    preds = [[EvalComment("auth.py", 10, "security")]]
    truths = [[EvalComment("auth.py", 12, "security")]]
    result = scorer.score_dataset(preds, truths)
    assert result.per_category["security"].f1 == 1.0


def test_line_tolerance_exceeded():
    scorer = EvalScorer(line_tolerance=5)
    preds = [[EvalComment("auth.py", 10, "security")]]
    truths = [[EvalComment("auth.py", 20, "security")]]
    result = scorer.score_dataset(preds, truths)
    assert result.per_category["security"].true_positives == 0


def test_category_mismatch():
    scorer = EvalScorer(line_tolerance=5)
    preds = [[EvalComment("auth.py", 10, "style")]]
    truths = [[EvalComment("auth.py", 10, "security")]]
    result = scorer.score_dataset(preds, truths)
    assert result.per_category["security"].false_negatives == 1
    assert result.per_category["style"].false_positives == 1


def test_empty_predictions():
    scorer = EvalScorer()
    preds = [[]]
    truths = [[EvalComment("auth.py", 10, "bug")]]
    result = scorer.score_dataset(preds, truths)
    assert result.per_category["bug"].false_negatives == 1
    assert result.overall_recall == 0.0
