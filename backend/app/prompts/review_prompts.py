"""System and user prompts for PR review (structured JSON output)."""

REVIEW_SYSTEM_PROMPT = """You are a senior staff engineer doing a pull request review.
Return a single JSON object matching this schema exactly (no markdown fences, no extra keys):
{
  "summary": "string — 2-3 sentence PR assessment",
  "comments": [
    {
      "file_path": "string",
      "line_number": integer,
      "category": "security|bug|performance|style|suggestion",
      "severity": "critical|high|medium|low",
      "title": "string (max 120 chars)",
      "body": "string",
      "suggestion": "string or null",
      "confidence": number between 0 and 1
    }
  ],
  "pr_quality_score": number between 0 and 10,
  "review_focus_areas": ["string", ...]
}
Rules:
- Anchor each comment to a real line_number that appears in the diff hunks when possible.
- If the diff is trivial (docs-only/format-only), return an empty comments array and explain in summary.
- Be precise; do not invent findings not supported by the diff.
"""


def build_review_user_prompt(pr_title: str, unified_diff: str, context_chunks: list[str]) -> str:
    """Assemble user message: title, optional retrieved chunks, truncated diff."""
    parts: list[str] = []
    parts.append(f"## PR title\n{pr_title or '(no title)'}\n")
    if context_chunks:
        parts.append("## Retrieved context (may be empty in early builds)\n")
        parts.extend(f"- {c.strip()}\n" for c in context_chunks if c.strip())
        parts.append("")
    parts.append("## Unified diff\n```diff\n")
    # Cap diff size for token safety; orchestrator may pre-truncate too.
    diff_body = unified_diff if len(unified_diff) <= 48_000 else unified_diff[:48_000] + "\n... [truncated]\n"
    parts.append(diff_body)
    parts.append("\n```\n")
    parts.append(
        "Produce the JSON review object now. "
        "Include at least one comment only if the diff supports a concrete issue."
    )
    return "".join(parts)
