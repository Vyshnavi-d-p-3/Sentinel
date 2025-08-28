"""Unit tests for the eval router disk-artifact helpers (no DB required)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import eval_router
from app.routers.eval_router import (
    _disk_results_detail,
    _disk_results_summary,
    _load_json,
)


def test_load_json_returns_none_for_missing_file(tmp_path: Path) -> None:
    assert _load_json(tmp_path / "nope.json") is None


def test_load_json_returns_none_for_malformed_file(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{not valid json")
    assert _load_json(path) is None


@pytest.fixture
def sample_payload() -> dict:
    """Real shape produced by scoring.DualEvalResult.summary()."""
    return {
        "prompt_hash": "abc1234",
        "model_version": "claude-sonnet-4",
        "dataset_version": "v1",
        "avg_latency_ms": 1234.0,
        "total_cost_usd": 0.42,
        "strict": {
            "overall": {"precision": 0.8, "recall": 0.7, "f1": 0.75},
            "total_prs": 3,
            "per_category": {
                "security": {"precision": 1.0, "recall": 0.5, "f1": 0.67},
            },
        },
        "soft": {
            "overall": {"precision": 0.9, "recall": 0.85, "f1": 0.87},
        },
        "clean_pr": {
            "total_clean_prs": 1,
            "clean_prs_with_any_comment": 0,
            "clean_pr_fp_rate": 0.0,
        },
        "per_pr": [{"pr_id": "pr-1", "skipped": False}],
    }


@pytest.fixture
def flat_payload() -> dict:
    """Legacy/DB shape where ``overall_*`` are flat keys."""
    return {
        "strict": {
            "overall_precision": 0.55,
            "overall_recall": 0.45,
            "overall_f1": 0.49,
        },
    }


def test_disk_results_summary_pulls_from_strict_block(sample_payload: dict) -> None:
    s = _disk_results_summary(sample_payload)
    assert s.source == "disk"
    assert s.overall_f1 == 0.75
    assert s.overall_precision == 0.8
    assert s.overall_recall == 0.7
    assert s.total_prs_evaluated == 3
    assert s.prompt_hash == "abc1234"


def test_disk_results_detail_preserves_sub_blocks(sample_payload: dict) -> None:
    d = _disk_results_detail(sample_payload)
    # The detail response flattens nested ``overall`` so the dashboard can read
    # ``block.overall_f1`` regardless of which shape was on disk.
    assert d.strict["overall_f1"] == 0.75
    assert d.soft["overall_f1"] == 0.87
    assert d.clean_pr["clean_pr_fp_rate"] == 0.0
    assert d.per_pr == [{"pr_id": "pr-1", "skipped": False}]


def test_disk_results_summary_accepts_flat_legacy_shape(flat_payload: dict) -> None:
    s = _disk_results_summary(flat_payload)
    assert s.overall_f1 == 0.49
    assert s.overall_precision == 0.55
    assert s.overall_recall == 0.45


def test_disk_payload_round_trips_through_json(tmp_path: Path, sample_payload: dict) -> None:
    """Smoke: write to disk, load back, and re-parse."""
    path = tmp_path / "results.json"
    path.write_text(json.dumps(sample_payload))
    loaded = _load_json(path)
    assert loaded is not None
    s = _disk_results_summary(loaded)
    assert s.overall_f1 == 0.75


def test_eval_dir_points_at_repo_eval_folder() -> None:
    # Guard against regression where the module-level path calculation diverges
    # from the repo layout.
    assert eval_router._EVAL_DIR.name == "eval"


@pytest.fixture
def api_client() -> TestClient:
    return TestClient(app)


def test_trigger_eval_returns_403_when_disabled(api_client: TestClient) -> None:
    with patch.object(eval_router.settings, "eval_trigger_enabled", False):
        resp = api_client.post("/api/v1/eval/trigger")
    assert resp.status_code == 403
    body = resp.json()
    assert body["detail"]["error"] == "eval_trigger_disabled"


def test_trigger_eval_returns_summary_when_enabled_and_runner_ok(
    api_client: TestClient,
    sample_payload: dict,
) -> None:
    fake_summary = eval_router._disk_results_summary(sample_payload)

    async def _noop_runner() -> tuple[int, bytes, bytes]:
        return 0, b"done\n", b""

    with (
        patch.object(eval_router.settings, "eval_trigger_enabled", True),
        patch.object(eval_router.settings, "eval_trigger_force_mock", True),
        patch(
            "app.routers.eval_router._run_eval_runner_subprocess",
            new=AsyncMock(side_effect=_noop_runner),
        ),
        patch(
            "app.routers.eval_router._load_json",
            return_value=sample_payload,
        ),
    ):
        resp = api_client.post("/api/v1/eval/trigger")

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "completed"
    assert data["exit_code"] == 0
    assert data["forced_mock_llm"] is True
    assert data["summary"]["overall_f1"] == fake_summary.overall_f1
