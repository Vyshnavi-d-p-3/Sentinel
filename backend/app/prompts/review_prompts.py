"""
Prompts for the agentic 4-step review pipeline.

Step 1 — File triage: classify each changed file as high/medium/low/skip risk.
Step 2 — Deep review:  per high/medium-risk file, produce structured comments.
Step 3 — Cross-ref:    look across all step-2 findings for multi-file issues.
Step 4 — Synthesis:    summary + quality score + focus areas.

Every prompt template is hashed together via ``review_prompt_template_hash``
so each persisted review and eval run is reproducibly tied to the exact prompt
set that produced it.
"""

from __future__ import annotations

import hashlib
import json

# ---------------------------------------------------------------------------
# Step 1 — Triage
# ---------------------------------------------------------------------------

TRIAGE_SYSTEM_PROMPT = """You are a senior staff engineer triaging files in a pull request.
Classify EVERY changed file by review risk. Skip lockfiles, generated code, snapshots,
formatter-only changes, and trivial doc tweaks. Mark anything touching auth, payments,
data access, or public APIs as high risk.

Return a single JSON object matching this schema exactly (no markdown fences, no extra keys):
{
  "files": [
    {
      "file_path": "string",
      "risk": "high|medium|low|skip",
      "reasoning": "string (why this risk level)",
      "lines_changed": integer
    }
  ],
  "total_files": integer,
  "files_to_review": integer  // count of files with risk in {high, medium}
}
Rules:
- Include every file present in the diff, in the same order.
- Be conservative: when in doubt, prefer "medium" over "low".
- Reasoning must be concrete (mention the function/module/topic), not generic.
"""

_TRIAGE_USER_TEMPLATE_VERSION = "build_triage_user_prompt:v1"


def build_triage_user_prompt(pr_title: str, file_summaries: list[dict]) -> str:
    """
    Build the triage user message from a list of per-file summaries.

    Each summary should look like:
        {"path": "...", "additions": 3, "deletions": 1, "status": "modified",
         "preview": "first ~40 lines of the file's diff hunks"}
    """
    payload = {
        "pr_title": pr_title or "(no title)",
        "files": file_summaries,
    }
    body = json.dumps(payload, indent=2, default=str)
    return (
        "Triage every file below. Return the JSON object described in the system prompt.\n\n"
        f"{body}\n"
    )


# ---------------------------------------------------------------------------
# Step 2 — Deep review (per file)
# ---------------------------------------------------------------------------

REVIEW_SYSTEM_PROMPT = """You are a senior staff engineer doing a pull request review.
Review ONE file at a time. Return a single JSON object matching this schema exactly
(no markdown fences, no extra keys):
{
  "file_path": "string",
  "comments": [
    {
      "file_path": "string",
      "line_number": integer,
      "category": "security|bug|performance|style|suggestion",
      "severity": "critical|high|medium|low",
      "title": "string (max 120 chars)",
      "body": "string",
      "suggestion": "string or null",
      "confidence": number between 0 and 1,
      "related_files": []
    }
  ]
}
Rules:
- Anchor every comment to a real line_number that appears in the diff hunks.
- Prefer FEWER high-quality comments over many low-quality ones.
- Do NOT flag missing tests, formatting that matches project style, or acknowledged TODOs.
- Rate confidence honestly. If unsure, use 0.3-0.5, not 0.9.
- Zero comments is a valid output. If the file looks correct, return an empty comments array.
- Use file_path identical to the file under review.
"""

_USER_PROMPT_TEMPLATE_VERSION = "build_review_user_prompt:v2"


def build_review_user_prompt(
    pr_title: str,
    unified_diff: str,
    context_chunks: list[str],
    file_path: str | None = None,
) -> str:
    """Assemble the per-file deep-review user message."""
    parts: list[str] = []
    parts.append(f"## PR title\n{pr_title or '(no title)'}\n")
    if file_path:
        parts.append(f"## File under review\n{file_path}\n")
    if context_chunks:
        parts.append("## Retrieved context (may be empty in early builds)\n")
        parts.extend(f"- {c.strip()}\n" for c in context_chunks if c.strip())
        parts.append("")
    parts.append("## Unified diff\n```diff\n")
    diff_body = unified_diff if len(unified_diff) <= 48_000 else unified_diff[:48_000] + "\n... [truncated]\n"
    parts.append(diff_body)
    parts.append("\n```\n")
    parts.append(
        "Produce the JSON review object now. "
        "Include at least one comment only if the diff supports a concrete issue."
    )
    return "".join(parts)


# ---------------------------------------------------------------------------
# Step 3 — Cross-reference
# ---------------------------------------------------------------------------

CROSSREF_SYSTEM_PROMPT = """You are a senior staff engineer looking for cross-file issues
that single-file review missed: API signature changes with uncaught callers, type
mismatches across module boundaries, inconsistent error handling, duplicate logic, and
broken contracts between layers.

Return a single JSON object matching this schema exactly (no markdown fences, no extra keys):
{
  "comments": [
    {
      "file_path": "string",                // primary file the comment anchors to
      "line_number": integer,
      "category": "security|bug|performance|style|suggestion",
      "severity": "critical|high|medium|low",
      "title": "string (max 120 chars)",
      "body": "string explaining the cross-file issue",
      "suggestion": "string or null",
      "confidence": number between 0 and 1,
      "related_files": ["string", ...]      // ALL involved file paths (>=2)
    }
  ]
}
Rules:
- Only emit comments that genuinely span ≥2 files. Do not duplicate per-file findings.
- Prefer empty comments array over speculation.
- related_files must be non-empty for every cross-file finding.
"""

_CROSSREF_USER_TEMPLATE_VERSION = "build_crossref_user_prompt:v1"


def build_crossref_user_prompt(per_file_findings: list[dict]) -> str:
    """Build the cross-reference user message from collected per-file findings."""
    payload = {"per_file_findings": per_file_findings}
    body = json.dumps(payload, indent=2, default=str)
    return (
        "Look across these per-file findings for genuine multi-file issues. "
        "Return the JSON object described in the system prompt.\n\n"
        f"{body}\n"
    )


# ---------------------------------------------------------------------------
# Step 4 — Synthesis
# ---------------------------------------------------------------------------

SYNTHESIS_SYSTEM_PROMPT = """You are summarizing a completed code review for a busy
human reviewer. Produce a single JSON object matching this schema exactly
(no markdown fences, no extra keys):
{
  "summary": "string — 2-3 sentence PR assessment",
  "pr_quality_score": number between 0 and 10,
  "review_focus_areas": ["string", ...]
}
Rules:
- Quality score reflects merge-readiness: 9-10 = ship, 6-8 = needs revision,
  3-5 = significant work needed, 0-2 = should not merge.
- review_focus_areas should list concrete topics the human reviewer must double-check
  (e.g. "auth changes in `middleware.py`", "DB migration ordering").
- Be honest: do not inflate the score because the diff is small.
"""

_SYNTHESIS_USER_TEMPLATE_VERSION = "build_synthesis_user_prompt:v1"


def build_synthesis_user_prompt(
    pr_title: str,
    triage_summary: dict,
    all_comments: list[dict],
) -> str:
    """Build the synthesis user message from triage + all collected comments."""
    payload = {
        "pr_title": pr_title or "(no title)",
        "triage_summary": triage_summary,
        "all_comments": all_comments,
    }
    body = json.dumps(payload, indent=2, default=str)
    return (
        "Synthesize the final review summary, quality score, and focus areas.\n\n"
        f"{body}\n"
    )


# ---------------------------------------------------------------------------
# Reproducibility — single hash over every prompt template version
# ---------------------------------------------------------------------------

def review_prompt_template_hash() -> str:
    """Stable hash linking persisted reviews to the active prompt set."""
    payload = "\n".join(
        [
            TRIAGE_SYSTEM_PROMPT,
            _TRIAGE_USER_TEMPLATE_VERSION,
            REVIEW_SYSTEM_PROMPT,
            _USER_PROMPT_TEMPLATE_VERSION,
            CROSSREF_SYSTEM_PROMPT,
            _CROSSREF_USER_TEMPLATE_VERSION,
            SYNTHESIS_SYSTEM_PROMPT,
            _SYNTHESIS_USER_TEMPLATE_VERSION,
        ]
    )
    return hashlib.sha256(payload.encode()).hexdigest()
