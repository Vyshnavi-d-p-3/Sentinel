"""Codebase health analytics over historical review and feedback data."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

_SEVERITY_WEIGHT = {"critical": 4, "high": 3, "medium": 1, "low": 1}
_MODULE_PENALTY = {"critical": 15, "high": 10, "medium": 5, "low": 2}
_CATEGORIES = ("security", "bug", "performance", "style", "suggestion")


@dataclass
class FileHotspot:
    file_path: str
    findings: int
    critical: int
    high: int
    medium: int
    low: int
    prs_affected: int
    risk_score: int


@dataclass
class RecurringPattern:
    category: str
    signature: str
    occurrences: int
    prs_affected: int
    files_affected: list[str]


@dataclass
class ModuleHealth:
    module: str
    findings: int
    critical: int
    high: int
    medium: int
    low: int
    health_score: int


@dataclass
class ReviewImpact:
    resolved: int
    dismissed: int
    resolution_rate: float
    per_category_rates: dict[str, float]
    most_valued_category: str | None = None


@dataclass
class ComplexityBucket:
    bucket: str
    pr_count: int
    avg_tokens: float
    avg_findings: float


@dataclass
class HealthReport:
    hotspots: list[FileHotspot] = field(default_factory=list)
    trends: list[dict[str, Any]] = field(default_factory=list)
    patterns: list[RecurringPattern] = field(default_factory=list)
    impact: ReviewImpact | None = None
    modules: list[ModuleHealth] = field(default_factory=list)
    complexity: list[ComplexityBucket] = field(default_factory=list)
    insights: list[str] = field(default_factory=list)
    total_prs_reviewed: int = 0
    total_findings: int = 0


class HealthIntelligenceEngine:
    """Aggregates review findings into health intelligence signals."""

    def analyze(
        self,
        reviews: list[dict[str, Any]],
        feedback: list[dict[str, Any]],
        period_days: int,
    ) -> HealthReport:
        hotspots = self._compute_hotspots(reviews)
        trends = self._compute_trends(reviews)
        patterns = self._compute_patterns(reviews)
        modules = self._compute_module_health(reviews)
        impact = self._compute_review_impact(feedback)
        complexity = self._compute_complexity(reviews)
        total_findings = sum(len(r.get("comments") or []) for r in reviews)
        report = HealthReport(
            hotspots=hotspots,
            trends=trends,
            patterns=patterns,
            impact=impact,
            modules=modules,
            complexity=complexity,
            insights=[],
            total_prs_reviewed=len(reviews),
            total_findings=total_findings,
        )
        report.insights = self._generate_insights(report, period_days)
        return report

    def _compute_hotspots(self, reviews: list[dict[str, Any]]) -> list[FileHotspot]:
        by_file: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "findings": 0,
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
                "risk_score": 0,
                "pr_ids": set(),
            }
        )
        for review in reviews:
            pr_id = str(review.get("id") or review.get("pr_number") or "unknown")
            for c in review.get("comments") or []:
                if not isinstance(c, dict):
                    continue
                path = str(c.get("file_path") or "unknown")
                sev = str(c.get("severity") or "low").lower()
                slot = by_file[path]
                slot["findings"] += 1
                if sev in ("critical", "high", "medium", "low"):
                    slot[sev] += 1
                slot["risk_score"] += _SEVERITY_WEIGHT.get(sev, 1)
                slot["pr_ids"].add(pr_id)
        out = [
            FileHotspot(
                file_path=file_path,
                findings=int(v["findings"]),
                critical=int(v["critical"]),
                high=int(v["high"]),
                medium=int(v["medium"]),
                low=int(v["low"]),
                prs_affected=len(v["pr_ids"]),
                risk_score=int(v["risk_score"]),
            )
            for file_path, v in by_file.items()
        ]
        return sorted(out, key=lambda x: (x.risk_score, x.findings), reverse=True)

    def _compute_trends(self, reviews: list[dict[str, Any]]) -> list[dict[str, Any]]:
        weekly: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for review in reviews:
            created = review.get("created_at")
            if not isinstance(created, datetime):
                continue
            week_start = created.date().strftime("%Y-%m-%d")
            for c in review.get("comments") or []:
                if not isinstance(c, dict):
                    continue
                cat = str(c.get("category") or "unknown").lower()
                weekly[week_start][cat] += 1
        out: list[dict[str, Any]] = []
        for week, counts in sorted(weekly.items()):
            row = {"week_start": week, "total": sum(counts.values())}
            for c in _CATEGORIES:
                row[c] = int(counts.get(c, 0))
            out.append(row)
        return out

    def _compute_patterns(self, reviews: list[dict[str, Any]]) -> list[RecurringPattern]:
        grouped: dict[tuple[str, str], dict[str, Any]] = defaultdict(
            lambda: {"occurrences": 0, "pr_ids": set(), "files": set()}
        )
        for review in reviews:
            pr_id = str(review.get("id") or review.get("pr_number") or "unknown")
            for c in review.get("comments") or []:
                if not isinstance(c, dict):
                    continue
                category = str(c.get("category") or "unknown").lower()
                title = str(c.get("title") or c.get("body") or "").lower()
                signature = self._pattern_signature(title)
                if not signature:
                    continue
                bucket = grouped[(category, signature)]
                bucket["occurrences"] += 1
                bucket["pr_ids"].add(pr_id)
                bucket["files"].add(str(c.get("file_path") or "unknown"))

        patterns: list[RecurringPattern] = []
        for (category, signature), v in grouped.items():
            prs_affected = len(v["pr_ids"])
            if prs_affected < 2:
                continue
            patterns.append(
                RecurringPattern(
                    category=category,
                    signature=signature,
                    occurrences=int(v["occurrences"]),
                    prs_affected=prs_affected,
                    files_affected=sorted(v["files"]),
                )
            )
        return sorted(patterns, key=lambda p: (p.prs_affected, p.occurrences), reverse=True)

    @staticmethod
    def _pattern_signature(text: str) -> str:
        if "sql injection" in text or ("sql" in text and "injection" in text):
            return "sql injection"
        if "xss" in text or "cross site scripting" in text:
            return "xss"
        if "race condition" in text:
            return "race condition"
        words = [w for w in re.findall(r"[a-z]{4,}", text.lower()) if w not in {"that", "with", "this", "from", "into"}]
        return " ".join(words[:3]) if words else ""

    def _compute_module_health(self, reviews: list[dict[str, Any]]) -> list[ModuleHealth]:
        by_mod: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for review in reviews:
            for c in review.get("comments") or []:
                if not isinstance(c, dict):
                    continue
                path = str(c.get("file_path") or "")
                module = self._module_name(path)
                sev = str(c.get("severity") or "low").lower()
                by_mod[module]["findings"] += 1
                if sev in ("critical", "high", "medium", "low"):
                    by_mod[module][sev] += 1
        out: list[ModuleHealth] = []
        for mod, c in by_mod.items():
            penalty = (
                c.get("critical", 0) * _MODULE_PENALTY["critical"]
                + c.get("high", 0) * _MODULE_PENALTY["high"]
                + c.get("medium", 0) * _MODULE_PENALTY["medium"]
                + c.get("low", 0) * _MODULE_PENALTY["low"]
            )
            out.append(
                ModuleHealth(
                    module=mod,
                    findings=int(c.get("findings", 0)),
                    critical=int(c.get("critical", 0)),
                    high=int(c.get("high", 0)),
                    medium=int(c.get("medium", 0)),
                    low=int(c.get("low", 0)),
                    health_score=max(0, 100 - penalty),
                )
            )
        return sorted(out, key=lambda m: (m.health_score, -m.findings))

    @staticmethod
    def _module_name(path: str) -> str:
        if not path or "/" not in path:
            return "root"
        return path.split("/", 1)[0]

    def _compute_review_impact(self, feedback: list[dict[str, Any]]) -> ReviewImpact | None:
        if not feedback:
            return None
        resolved = sum(1 for f in feedback if str(f.get("action")) == "resolved")
        dismissed = sum(1 for f in feedback if str(f.get("action")) == "dismissed")
        denom = resolved + dismissed
        resolution_rate = float(resolved / denom) if denom else 0.0

        per_cat_counts: dict[str, dict[str, int]] = defaultdict(lambda: {"resolved": 0, "dismissed": 0})
        for row in feedback:
            cat = str(row.get("category") or "unknown").lower()
            action = str(row.get("action") or "")
            if action not in ("resolved", "dismissed"):
                continue
            per_cat_counts[cat][action] += 1
        rates: dict[str, float] = {}
        for cat, c in per_cat_counts.items():
            d = c["resolved"] + c["dismissed"]
            rates[cat] = float(c["resolved"] / d) if d else 0.0
        best_cat = max(rates.items(), key=lambda kv: kv[1])[0] if rates else None
        return ReviewImpact(
            resolved=resolved,
            dismissed=dismissed,
            resolution_rate=resolution_rate,
            per_category_rates=rates,
            most_valued_category=best_cat,
        )

    def _compute_complexity(self, reviews: list[dict[str, Any]]) -> list[ComplexityBucket]:
        # Use total_tokens as a stable complexity proxy across historical reviews.
        bins = {
            "small": (0, 3000),
            "medium": (3001, 8000),
            "large": (8001, 20000),
            "xl": (20001, 10**9),
        }
        bucket_rows: dict[str, list[tuple[int, int]]] = defaultdict(list)
        for r in reviews:
            tokens = int(r.get("total_tokens") or 0)
            findings = len(r.get("comments") or [])
            for name, (lo, hi) in bins.items():
                if lo <= tokens <= hi:
                    bucket_rows[name].append((tokens, findings))
                    break
        out: list[ComplexityBucket] = []
        for name in ("small", "medium", "large", "xl"):
            rows = bucket_rows.get(name, [])
            if not rows:
                out.append(ComplexityBucket(bucket=name, pr_count=0, avg_tokens=0.0, avg_findings=0.0))
                continue
            out.append(
                ComplexityBucket(
                    bucket=name,
                    pr_count=len(rows),
                    avg_tokens=sum(r[0] for r in rows) / len(rows),
                    avg_findings=sum(r[1] for r in rows) / len(rows),
                )
            )
        return out

    def _generate_insights(self, report: HealthReport, period_days: int) -> list[str]:
        insights: list[str] = []
        if report.total_prs_reviewed == 0:
            return [f"No reviews found in the last {period_days} days. Health intelligence will populate after review activity."]

        if report.hotspots:
            top = report.hotspots[0]
            insights.append(
                f"{top.file_path} has {top.findings} findings across {top.prs_affected} PRs (risk score {top.risk_score}) — consider focused refactoring."
            )
        if report.patterns:
            p = report.patterns[0]
            insights.append(
                f"Recurring {p.category} pattern '{p.signature}' appears in {p.prs_affected} PRs — add guardrails/tests to prevent repeats."
            )
        if report.modules:
            weak = min(report.modules, key=lambda m: m.health_score)
            if weak.health_score < 70:
                insights.append(
                    f"Module {weak.module} scores {weak.health_score}/100 health with {weak.findings} findings — prioritize stabilization."
                )
        if report.impact is not None:
            insights.append(
                f"Feedback resolution rate is {report.impact.resolution_rate:.0%} ({report.impact.resolved} resolved, {report.impact.dismissed} dismissed)."
            )
        if report.complexity:
            non_empty = [b for b in report.complexity if b.pr_count > 0]
            if len(non_empty) >= 2:
                small = next((b for b in non_empty if b.bucket == "small"), None)
                large = next((b for b in non_empty if b.bucket in ("large", "xl")), None)
                if small and large and large.avg_findings > small.avg_findings:
                    insights.append(
                        "Larger PRs show higher average findings than small PRs — encourage smaller, reviewable changes."
                    )
        if not insights:
            insights.append("Health signals look stable for this period with no dominant hotspot or recurring pattern.")
        return insights


def report_to_dict(report: HealthReport) -> dict[str, Any]:
    """Serialize dataclass report for API responses."""
    return asdict(report)
