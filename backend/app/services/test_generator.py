"""Step 5 Smart Test Generator service."""

from __future__ import annotations

import time
from dataclasses import dataclass

from app.models.review_output import ReviewComment, Severity
from app.models.test_output import TestGenerationOutput
from app.prompts.testgen_prompts import TESTGEN_SYSTEM_PROMPT, build_testgen_user_prompt
from app.services.llm_gateway import LLMGateway
from app.services.orchestrator_types import PipelineStepUsage
from app.services.pricing import estimate_llm_cost_usd, split_estimated_tokens

_SEVERITY_RANK = {
    Severity.CRITICAL: 0,
    Severity.HIGH: 1,
    Severity.MEDIUM: 2,
    Severity.LOW: 3,
}
_ALLOWED_CATEGORIES = {"security", "bug", "performance"}
# NOTE: Confidence calibration for generated tests is even worse than
# for review comments. We filter at 0.3 but should track accuracy.


@dataclass
class TestGenerationResult:
    output: TestGenerationOutput
    usage: PipelineStepUsage
    error: str | None = None


class TestGenerator:
    """Generate structured regression tests from review findings."""

    __test__ = False

    def __init__(self, llm_gateway: LLMGateway | None = None) -> None:
        self.llm = llm_gateway or LLMGateway()

    @staticmethod
    def _is_eligible(comment: ReviewComment) -> bool:
        return (
            _SEVERITY_RANK.get(comment.severity, 99) <= _SEVERITY_RANK[Severity.MEDIUM]
            and comment.category.value in _ALLOWED_CATEGORIES
        )

    async def generate(
        self,
        pr_title: str,
        comments: list[ReviewComment],
        file_diffs: dict[str, str],
    ) -> TestGenerationResult:
        eligible = [c for c in comments if self._is_eligible(c)]
        started = time.monotonic()
        if not eligible:
            output = TestGenerationOutput(
                tests=[],
                total_comments_eligible=0,
                total_tests_generated=0,
                skipped_reasons=["No eligible findings (need severity >= medium and category in security/bug/performance)."],
            )
            usage = PipelineStepUsage(
                step="testgen",
                model_version="skipped",
                input_tokens=0,
                output_tokens=0,
                cost_usd=0.0,
                latency_ms=int((time.monotonic() - started) * 1000),
            )
            return TestGenerationResult(output=output, usage=usage)

        user_prompt = build_testgen_user_prompt(
            pr_title,
            comments=[c.model_dump(mode="json") for c in eligible],
            file_diffs=file_diffs,
        )
        try:
            output, total_tokens, model_version = await self.llm.call_structured(
                step_name="testgen",
                system_prompt=TESTGEN_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                response_model=TestGenerationOutput,
                temperature=0.0,
            )
        except Exception as exc:
            usage = PipelineStepUsage(
                step="testgen",
                model_version="error",
                input_tokens=0,
                output_tokens=0,
                cost_usd=0.0,
                latency_ms=int((time.monotonic() - started) * 1000),
            )
            return TestGenerationResult(
                output=TestGenerationOutput(
                    tests=[],
                    total_comments_eligible=len(eligible),
                    total_tests_generated=0,
                    skipped_reasons=["LLM call failed."],
                ),
                usage=usage,
                error=str(exc),
            )

        input_tokens, output_tokens = split_estimated_tokens(total_tokens)
        usage = PipelineStepUsage(
            step="testgen",
            model_version=model_version,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=estimate_llm_cost_usd(model_version, input_tokens, output_tokens),
            latency_ms=int((time.monotonic() - started) * 1000),
        )
        return TestGenerationResult(output=output, usage=usage)
