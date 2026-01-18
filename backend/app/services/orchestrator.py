"""
Review orchestrator — coordinates the full review pipeline.

Flow: parse diff → retrieve context → check budget → call LLM → post to GitHub.
"""

import hashlib
import logging
import time

from app.services.diff_parser import DiffParser
from app.services.cost_guard import CostGuard
from app.services.llm_gateway import LLMGateway
from app.models.review_output import ReviewOutput

logger = logging.getLogger(__name__)


class ReviewOrchestrator:
    """
    Coordinates the end-to-end review pipeline.

    Each review goes through:
    1. Parse the PR diff into structured file changes
    2. Retrieve relevant code context (hybrid BM25 + dense)
    3. Check cost budget — skip if exhausted
    4. Call LLM with diff + context → structured ReviewOutput
    5. Post comments to GitHub via Check Runs API
    6. Log cost + latency to database
    """

    def __init__(
        self,
        diff_parser: DiffParser | None = None,
        cost_guard: CostGuard | None = None,
        llm_gateway: LLMGateway | None = None,
    ):
        self.diff_parser = diff_parser or DiffParser()
        self.cost_guard = cost_guard or CostGuard()
        self.llm_gateway = llm_gateway or LLMGateway()

    async def review_pr(
        self,
        repo_id: str,
        pr_number: int,
        raw_diff: str,
        pr_title: str = "",
    ) -> ReviewOutput | None:
        """
        Execute the full review pipeline for a pull request.

        Returns None if the review was skipped (budget, empty diff, etc.)
        """
        start = time.monotonic()

        # 1. Parse diff
        parsed = self.diff_parser.parse(raw_diff)
        if not parsed.files or not parsed.has_code_changes:
            logger.info(f"PR #{pr_number}: no code changes, skipping")
            return None

        # 2. Estimate tokens and check budget
        estimated_tokens = self._estimate_tokens(parsed)
        allowed, reason = self.cost_guard.can_review(repo_id, estimated_tokens)
        if not allowed:
            logger.warning(f"PR #{pr_number}: skipped — {reason}")
            return None

        # 3. Retrieve context
        # TODO: Call hybrid retriever (BM25 + dense + RRF)
        context_chunks: list[str] = []

        # 4. Assemble prompt and call LLM
        try:
            diff_hash = hashlib.sha256(raw_diff.encode()).hexdigest()[:16]
            # TODO: Load active prompt template
            # TODO: Format with diff + context
            # TODO: Call LLM gateway
            # result = await self.llm_gateway.generate(...)
            logger.info(f"PR #{pr_number}: review pipeline not yet fully implemented")
            return None
        except Exception as e:
            self.cost_guard.record_failure()
            logger.error(f"PR #{pr_number}: review failed — {e}")
            return None

    def _estimate_tokens(self, parsed) -> int:
        """Rough token estimate: ~4 chars per token for code."""
        total_chars = sum(
            f.additions * 80 + f.deletions * 80  # avg 80 chars per line
            for f in parsed.files
        )
        return total_chars // 4
