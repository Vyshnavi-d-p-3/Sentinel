"""Unit tests for the prompts router helpers (no DB required)."""

from __future__ import annotations

from app.prompts.review_prompts import review_prompt_template_hash
from app.routers.prompts import _in_memory_prompt, _unified_diff


def test_in_memory_prompt_uses_real_template_hash() -> None:
    card = _in_memory_prompt()
    assert card.hash == review_prompt_template_hash()
    assert card.source == "code"
    assert card.is_active is True
    assert "Step 1 — Triage" in card.system_prompt
    assert "Step 4 — Synthesis" in card.system_prompt


def test_unified_diff_emits_standard_headers_and_hunks() -> None:
    a = "alpha\nbeta\ngamma\n"
    b = "alpha\nBETA\ngamma\n"
    diff = _unified_diff(a, b, fromfile="A/field", tofile="B/field")

    assert diff.startswith("--- A/field")
    assert "+++ B/field" in diff
    assert "-beta" in diff
    assert "+BETA" in diff


def test_unified_diff_empty_on_identical_input() -> None:
    same = "one\ntwo\nthree\n"
    diff = _unified_diff(same, same, fromfile="a", tofile="b")
    assert diff == ""
