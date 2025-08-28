"""Unit tests for feedback parsing and stat aggregation (no DB required)."""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

from app.services.feedback_tracker import (
    ACTION_DISMISSED,
    ACTION_REPLIED,
    ACTION_RESOLVED,
    compute_category_agreement,
    compute_daily_agreement,
    compute_overall_agreement,
    parse_pull_request_review_comment_event,
    parse_pull_request_review_event,
)


def _row(action: str, *, category: str | None, created_at: datetime) -> SimpleNamespace:
    """Lightweight stand-in for a ReviewFeedback ORM row."""
    return SimpleNamespace(action=action, category=category, created_at=created_at)


def test_review_dismissed_event_is_parsed() -> None:
    payload = {
        "action": "dismissed",
        "review": {"id": 7777, "user": {"login": "vyshu"}},
        "pull_request": {"number": 42},
        "repository": {"full_name": "owner/repo"},
    }
    parsed = parse_pull_request_review_event(payload)

    assert parsed is not None
    assert parsed.action == ACTION_DISMISSED
    assert parsed.repo_full_name == "owner/repo"
    assert parsed.pr_number == 42
    assert parsed.github_user == "vyshu"
    assert parsed.github_review_id == "7777"
    # Review-level dismiss has no specific inline comment.
    assert parsed.github_comment_id is None


def test_review_submitted_event_is_ignored() -> None:
    payload = {
        "action": "submitted",
        "review": {"id": 1, "user": {"login": "x"}},
        "pull_request": {"number": 1},
        "repository": {"full_name": "owner/repo"},
    }
    assert parse_pull_request_review_event(payload) is None


def test_inline_reply_event_targets_parent_comment() -> None:
    payload = {
        "action": "created",
        "comment": {
            "id": 9999,
            "in_reply_to_id": 1234,
            "body": "Good catch, fixing now",
            "user": {"login": "dev"},
            "path": "src/main.py",
            "line": 50,
            "pull_request_review_id": 5555,
        },
        "pull_request": {"number": 100},
        "repository": {"full_name": "owner/repo"},
    }
    parsed = parse_pull_request_review_comment_event(payload)

    assert parsed is not None
    assert parsed.action == ACTION_REPLIED
    assert parsed.github_comment_id == "1234"  # parent, not the reply itself
    assert parsed.reply_body == "Good catch, fixing now"
    assert parsed.inline_path == "src/main.py"
    assert parsed.inline_line == 50


def test_primary_inline_comment_without_parent_is_ignored() -> None:
    """A developer's first-level inline comment on their own PR is not feedback on Sentinel."""
    payload = {
        "action": "created",
        "comment": {"id": 1, "user": {"login": "x"}, "path": "a.py"},
        "pull_request": {"number": 1},
        "repository": {"full_name": "owner/repo"},
    }
    assert parse_pull_request_review_comment_event(payload) is None


def test_resolved_event_is_parsed() -> None:
    payload = {
        "action": "resolved",
        "comment": {"id": 42, "user": {"login": "dev"}, "path": "x.py"},
        "pull_request": {"number": 1},
        "repository": {"full_name": "owner/repo"},
    }
    parsed = parse_pull_request_review_comment_event(payload)
    assert parsed is not None
    assert parsed.action == ACTION_RESOLVED
    assert parsed.github_comment_id == "42"


def test_overall_agreement_uses_resolved_over_resolved_plus_dismissed() -> None:
    now = datetime.utcnow()
    rows = [
        _row(ACTION_RESOLVED, category="bug", created_at=now),
        _row(ACTION_RESOLVED, category="bug", created_at=now),
        _row(ACTION_RESOLVED, category="security", created_at=now),
        _row(ACTION_DISMISSED, category="style", created_at=now),
        _row(ACTION_REPLIED, category="bug", created_at=now),
    ]
    overall = compute_overall_agreement(rows)
    assert overall["resolved"] == 3
    assert overall["dismissed"] == 1
    assert overall["replied"] == 1
    # 3 / (3 + 1) = 0.75 — replies are intentionally excluded.
    assert overall["agreement_rate"] == 0.75


def test_category_agreement_breakdown_is_sorted_by_total_volume() -> None:
    now = datetime.utcnow()
    rows = [
        _row(ACTION_RESOLVED, category="bug", created_at=now),
        _row(ACTION_RESOLVED, category="bug", created_at=now),
        _row(ACTION_DISMISSED, category="bug", created_at=now),
        _row(ACTION_DISMISSED, category="style", created_at=now),
        _row(ACTION_DISMISSED, category="style", created_at=now),
    ]
    breakdown = compute_category_agreement(rows)

    assert [row["category"] for row in breakdown[:2]] == ["bug", "style"]
    bug = next(row for row in breakdown if row["category"] == "bug")
    style = next(row for row in breakdown if row["category"] == "style")
    assert bug["agreement_rate"] == 2 / 3
    assert style["agreement_rate"] == 0.0


def test_daily_agreement_window_excludes_old_events_and_pads_empty_days() -> None:
    end = datetime(2026, 4, 21, 12, 0, 0)
    rows = [
        _row(ACTION_RESOLVED, category="bug", created_at=end - timedelta(days=1)),
        _row(ACTION_DISMISSED, category="bug", created_at=end - timedelta(days=1)),
        _row(ACTION_RESOLVED, category="bug", created_at=end - timedelta(days=10)),  # outside window
    ]
    series = compute_daily_agreement(rows, days=3, end=end)

    # window=3 produces 4 buckets (today + 3 prior days), all with the date key set.
    assert len(series) == 4
    assert all("date" in entry for entry in series)
    by_date = {entry["date"]: entry for entry in series}
    yesterday = (end - timedelta(days=1)).date().isoformat()
    assert by_date[yesterday]["resolved"] == 1
    assert by_date[yesterday]["dismissed"] == 1
    assert by_date[yesterday]["agreement_rate"] == 0.5
    # Days outside the window contribute zero.
    assert all(entry["resolved"] == 0 for entry in series if entry["date"] != yesterday)


def test_empty_input_returns_zero_agreement_rate() -> None:
    overall = compute_overall_agreement([])
    assert overall["total_events"] == 0
    assert overall["agreement_rate"] == 0.0
