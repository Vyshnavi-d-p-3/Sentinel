"""
Tests for the eval ablation's StaticContextRetriever and the orchestrator's
retrieval wiring path.

The harness lives under ``eval/scripts``; we add it to sys.path so the test
sees the same imports the runner does.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "eval" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

os.environ.setdefault("LLM_MOCK_MODE", "true")

from static_retriever import StaticContextRetriever  # noqa: E402

from app.services.diff_parser import FileChange  # noqa: E402
from app.services.orchestrator import ReviewOrchestrator  # noqa: E402

SAMPLE_DIFF = """diff --git a/auth/session_factory.py b/auth/session_factory.py
--- a/auth/session_factory.py
+++ b/auth/session_factory.py
@@ -20,7 +20,7 @@
 def issue_session(user_id):
-    return Session(user_id=user_id, ttl=SESSION_TTL_SECONDS)
+    return Session(user_id=user_id, ttl=300)
"""


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def test_static_retriever_assembles_diff_then_context_in_order():
    retriever = StaticContextRetriever({
        "auth/session_factory.py": [
            "SESSION_TTL_SECONDS = 1800",
            "issue_refresh(token)  # depends on TTL",
        ],
    })
    file = FileChange(path="auth/session_factory.py", status="modified")

    result = _run(retriever.retrieve_for_file("repo-x", file, diff_text="DIFF_BODY"))

    text = result.context.text
    assert "# DIFF" in text
    assert "DIFF_BODY" in text
    # Context section appears after the diff section.
    assert text.index("# DIFF") < text.index("# CONTEXT 1 :: auth/session_factory.py")
    assert "SESSION_TTL_SECONDS = 1800" in text
    assert result.context.chunks_included == 2
    # Token bookkeeping is non-zero (char/4 heuristic).
    assert result.context.diff_tokens > 0
    assert result.context.chunk_tokens > 0


def test_static_retriever_returns_diff_only_when_no_chunks_for_path():
    retriever = StaticContextRetriever({"other/file.py": ["irrelevant"]})
    file = FileChange(path="auth/session_factory.py", status="modified")

    result = _run(retriever.retrieve_for_file("repo-x", file, diff_text="ONLY_THE_DIFF"))

    assert result.context.chunks_included == 0
    assert "ONLY_THE_DIFF" in result.context.text
    assert "CONTEXT" not in result.context.text


def test_static_retriever_empty_context_and_empty_diff_yields_blank_text():
    retriever = StaticContextRetriever({})
    file = FileChange(path="x.py", status="modified")

    result = _run(retriever.retrieve_for_file("repo-x", file, diff_text=""))

    assert result.context.text == ""
    assert result.context.chunks_included == 0
    assert result.context.total_tokens == 0


def test_orchestrator_records_retrieval_ms_when_static_retriever_wired():
    """The orchestrator's retrieval_ms telemetry must populate when a retriever is supplied."""
    retriever = StaticContextRetriever({
        "auth/session_factory.py": ["SESSION_TTL_SECONDS = 1800"],
    })
    orch = ReviewOrchestrator(retriever=retriever)

    result, reason = _run(orch.review_pr(
        repo_id="ablation-test",
        pr_number=1,
        raw_diff=SAMPLE_DIFF,
        pr_title="Shorten session TTL",
    ))

    assert result is not None, f"orchestrator skipped: {reason}"
    # retrieval_ms is an integer field on the result; with a wired retriever it
    # must be set (>= 0) and not None.
    assert isinstance(result.retrieval_ms, int)
    assert result.retrieval_ms >= 0


def test_orchestrator_without_retriever_reports_zero_retrieval_ms():
    """Baseline: no retriever wired => retrieval_ms stays at 0 (diff-only fallback)."""
    orch = ReviewOrchestrator(retriever=None)

    result, reason = _run(orch.review_pr(
        repo_id="ablation-test",
        pr_number=1,
        raw_diff=SAMPLE_DIFF,
        pr_title="Shorten session TTL",
    ))

    assert result is not None, f"orchestrator skipped: {reason}"
    assert result.retrieval_ms == 0
