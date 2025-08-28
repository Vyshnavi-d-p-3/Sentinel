"""
Agentic 4-step pipeline — verifies that ReviewOrchestrator emits the structures
that persistence/cost ledger code depends on (per-step timings, per-step usage,
triage result), using the deterministic mock LLM gateway.
"""

from __future__ import annotations

import asyncio
import os

os.environ.setdefault("LLM_MOCK_MODE", "true")

from app.services.orchestrator import ReviewOrchestrator  # noqa: E402

MULTI_FILE_DIFF = """diff --git a/src/auth.py b/src/auth.py
--- a/src/auth.py
+++ b/src/auth.py
@@ -10,3 +10,5 @@
 def login(user, password):
+    # placeholder
+    return user
diff --git a/src/db.py b/src/db.py
--- a/src/db.py
+++ b/src/db.py
@@ -5,2 +5,3 @@
 def query(name):
-    return db.execute(f"SELECT * FROM u WHERE n = '{name}'")
+    return db.execute("SELECT * FROM u WHERE n = %s", (name,))
"""


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def test_pipeline_runs_all_four_steps_and_records_per_step_telemetry():
    orch = ReviewOrchestrator()
    result, reason = _run(orch.review_pr(
        repo_id="unit-test",
        pr_number=1,
        raw_diff=MULTI_FILE_DIFF,
        pr_title="Multi-file mock",
    ))

    assert reason is None, reason
    assert result is not None

    # Triage produced one item per file.
    assert result.triage_result is not None
    assert result.triage_result["total_files"] == 2

    # Per-step timings keys.
    timings = result.pipeline_step_timings
    for key in ("triage_ms", "review_ms", "crossref_ms", "synthesis_ms"):
        assert key in timings, f"missing timing key: {key}"

    # Each per-file review + crossref + synthesis should produce a usage row.
    steps = [u.step for u in result.step_usages]
    assert "triage" in steps
    assert steps.count("review") >= 1
    assert "synthesis" in steps
    # Two files were reviewed → cross-ref step must have run.
    assert "crossref" in steps

    # Aggregated totals match per-step sums.
    assert result.input_tokens == sum(u.input_tokens for u in result.step_usages)
    assert result.output_tokens == sum(u.output_tokens for u in result.step_usages)
    assert result.total_tokens == result.input_tokens + result.output_tokens

    # Final ReviewOutput aggregates per-file comments.
    assert result.output.summary
    assert isinstance(result.output.review_focus_areas, list)
    assert isinstance(result.output.comments, list)


def test_pipeline_skips_crossref_when_only_one_file_reviewed():
    orch = ReviewOrchestrator()
    single_file_diff = """diff --git a/src/auth.py b/src/auth.py
--- a/src/auth.py
+++ b/src/auth.py
@@ -10,3 +10,4 @@
 def login(user, password):
+    return user
"""
    result, reason = _run(orch.review_pr(
        repo_id="unit-test",
        pr_number=2,
        raw_diff=single_file_diff,
        pr_title="Single file",
    ))
    assert reason is None
    assert result is not None
    steps = [u.step for u in result.step_usages]
    assert "crossref" not in steps
    assert result.pipeline_step_timings.get("crossref_ms") == 0


def test_pipeline_returns_skip_reason_for_empty_diff():
    orch = ReviewOrchestrator()
    result, reason = _run(orch.review_pr(
        repo_id="unit-test",
        pr_number=3,
        raw_diff="",
        pr_title="empty",
    ))
    assert result is None
    assert reason is not None
