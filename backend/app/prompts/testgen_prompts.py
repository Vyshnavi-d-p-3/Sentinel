"""Prompt templates for Step 5 Smart Test Generator."""

from __future__ import annotations

import json

_ELIGIBLE_SEVERITIES = {"critical", "high", "medium"}
_ELIGIBLE_CATEGORIES = {"security", "bug", "performance"}

TESTGEN_SYSTEM_PROMPT = """You are a senior test engineer generating regression tests for code review findings.
Generate complete, runnable tests that demonstrate the bug exists before the fix and passes after the fix.
Return a single JSON object matching this schema exactly (no markdown fences, no extra keys):
{
  "tests": [
    {
      "comment_title": "string",
      "file_path": "string",
      "test_file_path": "string",
      "framework": "pytest|jest|vitest|mocha|unittest",
      "test_code": "string",
      "test_name": "string",
      "description": "string",
      "category": "security|bug|performance|style|suggestion",
      "setup_notes": "string",
      "confidence": 0.0
    }
  ],
  "total_comments_eligible": integer,
  "total_tests_generated": integer,
  "skipped_reasons": ["string", "..."]
}
Rules:
- Only generate tests for findings with severity critical/high/medium.
- Skip style and suggestion categories.
- Zero tests is a valid output.
- Prefer deterministic tests with concrete assertions.
- Framework defaults:
  - Use pytest for `.py` files.
  - Use jest for `.js`/`.ts` files.
- Include imports and minimal setup in test_code.
"""


def build_testgen_user_prompt(
    pr_title: str,
    comments: list[dict],
    file_diffs: dict[str, str],
) -> str:
    """Build user payload with eligible findings and truncated per-file diffs."""
    eligible_comments = [
        c for c in comments
        if str(c.get("severity", "")).lower() in _ELIGIBLE_SEVERITIES
        and str(c.get("category", "")).lower() in _ELIGIBLE_CATEGORIES
    ]
    truncated_diffs = {
        path: diff[:4_000] + ("\n... [truncated]" if len(diff) > 4_000 else "")
        for path, diff in file_diffs.items()
    }
    payload = {
        "pr_title": pr_title or "(no title)",
        "eligible_comments": eligible_comments,
        "file_diffs": truncated_diffs,
    }
    return (
        "Generate regression tests for the eligible findings below and use per-file diffs as context.\n\n"
        f"{json.dumps(payload, indent=2, default=str)}\n"
    )
