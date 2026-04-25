"""Unit tests for Codebase Health Intelligence analytics."""

from __future__ import annotations

from datetime import datetime, timedelta

from app.services.health_intelligence import HealthIntelligenceEngine


def _review(
    review_id: str,
    *,
    days_ago: int = 0,
    tokens: int = 5000,
    comments: list[dict] | None = None,
) -> dict:
    return {
        "id": review_id,
        "pr_number": int(review_id.strip("r") or 0),
        "created_at": datetime.utcnow() - timedelta(days=days_ago),
        "total_tokens": tokens,
        "comments": comments or [],
    }


def _comment(file_path: str, category: str, severity: str, title: str) -> dict:
    return {
        "file_path": file_path,
        "category": category,
        "severity": severity,
        "title": title,
    }


class TestHealthReport:
    def test_analyze_returns_report(self) -> None:
        engine = HealthIntelligenceEngine()
        report = engine.analyze([_review("1", comments=[_comment("a.py", "bug", "high", "null bug")])], [], 30)
        assert report.total_prs_reviewed == 1
        assert report.total_findings == 1

    def test_empty_reviews_handled(self) -> None:
        engine = HealthIntelligenceEngine()
        report = engine.analyze([], [], 30)
        assert report.total_prs_reviewed == 0
        assert report.insights


class TestHotspots:
    def test_hotspot_ranking(self) -> None:
        engine = HealthIntelligenceEngine()
        reviews = [
            _review("1", comments=[_comment("hot.py", "bug", "critical", "panic"), _comment("x.py", "bug", "low", "nit")]),
            _review("2", comments=[_comment("hot.py", "security", "high", "sql injection")]),
        ]
        report = engine.analyze(reviews, [], 30)
        assert report.hotspots[0].file_path == "hot.py"

    def test_risk_score_calculation(self) -> None:
        engine = HealthIntelligenceEngine()
        reviews = [_review("1", comments=[_comment("a.py", "bug", "critical", "c"), _comment("a.py", "bug", "high", "h"), _comment("a.py", "bug", "low", "l")])]
        report = engine.analyze(reviews, [], 30)
        assert report.hotspots[0].risk_score == 8

    def test_unique_pr_counting(self) -> None:
        engine = HealthIntelligenceEngine()
        reviews = [
            _review("1", comments=[_comment("a.py", "bug", "high", "x"), _comment("a.py", "bug", "high", "y")]),
            _review("2", comments=[_comment("a.py", "bug", "high", "z")]),
        ]
        report = engine.analyze(reviews, [], 30)
        assert report.hotspots[0].prs_affected == 2


class TestCategoryTrends:
    def test_weekly_grouping(self) -> None:
        engine = HealthIntelligenceEngine()
        reviews = [
            _review("1", days_ago=1, comments=[_comment("a.py", "security", "high", "a")]),
            _review("2", days_ago=8, comments=[_comment("b.py", "bug", "high", "b")]),
        ]
        report = engine.analyze(reviews, [], 90)
        assert len(report.trends) >= 2

    def test_trend_totals(self) -> None:
        engine = HealthIntelligenceEngine()
        reviews = [_review("1", comments=[_comment("a.py", "security", "high", "a"), _comment("a.py", "bug", "medium", "b")])]
        report = engine.analyze(reviews, [], 30)
        assert report.trends[0]["total"] == 2


class TestRecurringPatterns:
    def test_detects_sql_injection_across_prs(self) -> None:
        engine = HealthIntelligenceEngine()
        reviews = [
            _review("1", comments=[_comment("a.py", "security", "high", "SQL injection risk")]),
            _review("2", comments=[_comment("b.py", "security", "high", "Fix sql injection now")]),
        ]
        report = engine.analyze(reviews, [], 90)
        assert any(p.signature == "sql injection" for p in report.patterns)

    def test_single_pr_pattern_excluded(self) -> None:
        engine = HealthIntelligenceEngine()
        reviews = [_review("1", comments=[_comment("a.py", "security", "high", "SQL injection risk")])]
        report = engine.analyze(reviews, [], 90)
        assert report.patterns == []


class TestReviewImpact:
    def test_resolution_rate(self) -> None:
        engine = HealthIntelligenceEngine()
        feedback = [{"action": "resolved", "category": "bug"}, {"action": "dismissed", "category": "bug"}]
        report = engine.analyze([], feedback, 30)
        assert report.impact is not None
        assert report.impact.resolution_rate == 0.5

    def test_per_category_rates(self) -> None:
        engine = HealthIntelligenceEngine()
        feedback = [{"action": "resolved", "category": "security"}, {"action": "dismissed", "category": "bug"}]
        report = engine.analyze([], feedback, 30)
        assert report.impact is not None
        assert report.impact.per_category_rates["security"] == 1.0

    def test_no_feedback_returns_none(self) -> None:
        engine = HealthIntelligenceEngine()
        report = engine.analyze([], [], 30)
        assert report.impact is None


class TestModuleHealth:
    def test_scores_present(self) -> None:
        engine = HealthIntelligenceEngine()
        reviews = [_review("1", comments=[_comment("app/auth.py", "security", "high", "a")])]
        report = engine.analyze(reviews, [], 30)
        assert report.modules

    def test_critical_penalty_calculation(self) -> None:
        engine = HealthIntelligenceEngine()
        reviews = [_review("1", comments=[_comment("app/auth.py", "security", "critical", "a")])]
        report = engine.analyze(reviews, [], 30)
        assert report.modules[0].health_score == 85


class TestComplexityCorrelation:
    def test_buckets_populated(self) -> None:
        engine = HealthIntelligenceEngine()
        reviews = [
            _review("1", tokens=1000, comments=[_comment("a.py", "bug", "low", "a")]),
            _review("2", tokens=10000, comments=[_comment("b.py", "bug", "high", "b")]),
        ]
        report = engine.analyze(reviews, [], 30)
        assert any(b.pr_count > 0 for b in report.complexity)

    def test_pr_counts(self) -> None:
        engine = HealthIntelligenceEngine()
        reviews = [_review("1", tokens=1000), _review("2", tokens=1000)]
        report = engine.analyze(reviews, [], 30)
        small = next(b for b in report.complexity if b.bucket == "small")
        assert small.pr_count == 2


class TestInsights:
    def test_generates_insights(self) -> None:
        engine = HealthIntelligenceEngine()
        reviews = [_review("1", comments=[_comment("app/auth.py", "security", "high", "SQL injection risk")])]
        report = engine.analyze(reviews, [{"action": "resolved", "category": "security"}], 30)
        assert len(report.insights) >= 1

    def test_empty_data_still_produces_message(self) -> None:
        engine = HealthIntelligenceEngine()
        report = engine.analyze([], [], 30)
        assert report.insights[0].startswith("No reviews found")
