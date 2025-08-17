"""
Review orchestrator — coordinates the full review pipeline.

Flow: parse diff → assemble context → check budget → call LLM → record usage.
"""

from __future__ import annotations

import hashlib
import logging
import time

from app.models.review_output import ReviewOutput
from app.prompts.review_prompts import REVIEW_SYSTEM_PROMPT, build_review_user_prompt
from app.services.cost_guard import CostGuard
from app.services.diff_parser import DiffParser
from app.services.llm_gateway import LLMGateway, LLMGatewayError

logger = logging.getLogger(__name__)

# Keep prompts + diff within a conservative budget before LLM call.
_MAX_DIFF_CHARS = 48_000
_MAX_CONTEXT_CHUNK = 2_000
_MAX_CONTEXT_CHUNKS = 8


class ReviewOrchestrator:
    def __init__(
        self,
        diff_parser: DiffParser | None = None,
        cost_guard: CostGuard | None = None,
        llm_gateway: LLMGateway | None = None,
    ):
        self.diff_parser = diff_parser or DiffParser()
        self.cost_guard = cost_guard or CostGuard()
        self.llm_gateway = llm_gateway or LLMGateway()

    def _context_from_parsed(self, raw_diff: str) -> list[str]:
        """Until BM25/pgvector are wired, use diff hunks as weak retrieval signal."""
        chunks: list[str] = []
        if not raw_diff.strip():
            return chunks
        body = raw_diff if len(raw_diff) <= _MAX_DIFF_CHARS else raw_diff[:_MAX_DIFF_CHARS]
        # Split on file headers to approximate chunks
        parts = body.split("\ndiff --git ")
        for i, part in enumerate(parts):
            piece = part if i == 0 else "diff --git " + part
            piece = piece.strip()
            if not piece:
                continue
            if len(piece) > _MAX_CONTEXT_CHUNK:
                piece = piece[:_MAX_CONTEXT_CHUNK] + "\n... [truncated]"
            chunks.append(piece)
            if len(chunks) >= _MAX_CONTEXT_CHUNKS:
                break
        return chunks

    async def review_pr(
        self,
        repo_id: str,
        pr_number: int,
        raw_diff: str,
        pr_title: str = "",
    ) -> tuple[ReviewOutput | None, str | None]:
        """
        Run the review pipeline.

        Returns ``(output, None)`` on success, or ``(None, reason)`` if skipped / failed.
        """
        start = time.monotonic()

        parsed = self.diff_parser.parse(raw_diff)
        if not parsed.files or not parsed.has_code_changes:
            return None, "no code changes in diff (or empty diff)"

        allowed, reason = self.cost_guard.can_review(repo_id, self._estimate_tokens(parsed, raw_diff))
        if not allowed:
            logger.warning("PR #%s: skipped — %s", pr_number, reason)
            return None, reason

        context_chunks = self._context_from_parsed(raw_diff)
        user_prompt = build_review_user_prompt(pr_title, raw_diff, context_chunks)

        try:
            result, est_tokens = await self.llm_gateway.generate(
                REVIEW_SYSTEM_PROMPT,
                user_prompt,
                ReviewOutput,
                temperature=0.0,
            )
        except LLMGatewayError as e:
            self.cost_guard.record_failure()
            logger.error("PR #%s: LLM failed — %s", pr_number, e)
            return None, f"llm error: {e}"

        self.cost_guard.record_usage(repo_id, est_tokens)
        elapsed_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            "PR #%s: review done in %sms tokens=%s diff_hash=%s",
            pr_number,
            elapsed_ms,
            est_tokens,
            hashlib.sha256(raw_diff.encode()).hexdigest()[:16],
        )
        return result, None

    def _estimate_tokens(self, parsed, raw_diff: str) -> int:
        """Rough token estimate for cost guard pre-check."""
        total_chars = sum(
            f.additions * 80 + f.deletions * 80 for f in parsed.files
        )
        diff_chars = min(len(raw_diff), _MAX_DIFF_CHARS)
        return (total_chars // 4) + (diff_chars // 4) + 2_000
