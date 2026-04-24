"""
Review orchestrator — the agentic 4-step review pipeline.

Step 1 — File triage:    classify each changed file as high/medium/low/skip.
Step 2 — Deep review:    per high/medium-risk file, produce structured comments.
Step 3 — Cross-reference: detect multi-file issues from collected step-2 findings.
Step 4 — Synthesis:      summary + quality score + focus areas.

Each step records its own latency, token usage, and USD cost so the persistence
layer can write per-step ``cost_ledger`` rows and populate the
``pipeline_step_timings`` JSONB on the review record.
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass

from app.config import settings
from app.models.review_output import (
    CrossReferenceOutput,
    FileReviewOutput,
    FileRisk,
    ReviewComment,
    ReviewOutput,
    ReviewSynthesis,
    TriageReport,
)
from app.prompts.review_prompts import (
    CROSSREF_SYSTEM_PROMPT,
    REVIEW_SYSTEM_PROMPT,
    SYNTHESIS_SYSTEM_PROMPT,
    TRIAGE_SYSTEM_PROMPT,
    build_crossref_user_prompt,
    build_review_user_prompt,
    build_synthesis_user_prompt,
    build_triage_user_prompt,
    review_prompt_template_hash,
)
from app.retrieval.hybrid import HybridRetriever
from app.services.cost_guard import CostGuard, CostGuardConfig
from app.services.diff_parser import DiffParser, FileChange, ParsedDiff
from app.services.llm_gateway import LLMGateway, LLMGatewayError
from app.services.orchestrator_types import OrchestratorResult, PipelineStepUsage
from app.services.pricing import estimate_llm_cost_usd, split_estimated_tokens

logger = logging.getLogger(__name__)

# Conservative caps to keep prompts within token budget per step.
_MAX_DIFF_CHARS = 48_000
_MAX_PER_FILE_DIFF_CHARS = 12_000
_MAX_TRIAGE_PREVIEW_CHARS = 1_500
_MAX_CONTEXT_CHUNK = 2_000
_MAX_CONTEXT_CHUNKS = 8


@dataclass
class _StepOutcome:
    """Internal helper bundling a step's parsed output + telemetry."""

    output: object | None
    usage: PipelineStepUsage
    error: str | None = None


class ReviewOrchestrator:
    def __init__(
        self,
        diff_parser: DiffParser | None = None,
        cost_guard: CostGuard | None = None,
        llm_gateway: LLMGateway | None = None,
        retriever: HybridRetriever | None = None,
    ):
        self.diff_parser = diff_parser or DiffParser()
        self.cost_guard = cost_guard or CostGuard(
            CostGuardConfig(
                daily_token_budget=int(settings.daily_token_budget),
                per_pr_token_cap=int(settings.per_pr_token_cap),
                circuit_breaker_threshold=int(settings.circuit_breaker_threshold),
                circuit_breaker_window_sec=int(settings.circuit_breaker_window_sec),
            )
        )
        self.llm_gateway = llm_gateway or LLMGateway()
        # Retrieval is optional. If no retriever is wired (e.g. unit tests with
        # no DB), step 2 falls back to diff-only context.
        self.retriever = retriever

    # ------------------------------------------------------------------ entry

    async def review_pr(
        self,
        repo_id: str,
        pr_number: int,
        raw_diff: str,
        pr_title: str = "",
    ) -> tuple[OrchestratorResult | None, str | None]:
        """
        Run the full agentic pipeline.

        Returns ``(result, None)`` on success or ``(None, reason)`` if skipped/failed.
        """
        start = time.monotonic()
        diff_hash = hashlib.sha256(raw_diff.encode()).hexdigest()
        prompt_hash = review_prompt_template_hash()

        parsed = self.diff_parser.parse(raw_diff)
        if not parsed.files or not parsed.has_code_changes:
            return None, "no code changes in diff (or empty diff)"

        allowed, reason = self.cost_guard.can_review(repo_id, self._estimate_tokens(parsed, raw_diff))
        if not allowed:
            logger.warning("PR #%s: skipped — %s", pr_number, reason)
            return None, reason

        per_file_diffs = self._split_diff_by_file(raw_diff)
        files_by_path = {f.path: f for f in parsed.files}
        step_usages: list[PipelineStepUsage] = []
        timings: dict[str, int] = {}
        retrieval_ms_total = 0

        # ---------------- Step 1: triage --------------------------------------
        triage = await self._run_triage(parsed, per_file_diffs, pr_title)
        step_usages.append(triage.usage)
        timings["triage_ms"] = triage.usage.latency_ms
        if triage.error:
            self.cost_guard.record_failure()
            return None, f"triage failed: {triage.error}"

        triage_report: TriageReport = triage.output  # type: ignore[assignment]
        files_to_review = self._select_files_to_review(triage_report, parsed)

        # ---------------- Step 2: per-file deep review ------------------------
        review_step_start = time.monotonic()
        all_comments: list[ReviewComment] = []
        per_file_findings: list[dict] = []
        review_input_tokens = 0
        review_output_tokens = 0
        review_cost = 0.0
        for file_path in files_to_review:
            file_diff = per_file_diffs.get(file_path) or ""
            if not file_diff.strip():
                continue
            file_change = files_by_path.get(file_path)
            outcome, file_retrieval_ms = await self._run_file_review(
                pr_title=pr_title,
                file_path=file_path,
                file_diff=file_diff,
                file_change=file_change,
                repo_id=repo_id,
            )
            retrieval_ms_total += file_retrieval_ms
            step_usages.append(outcome.usage)
            review_input_tokens += outcome.usage.input_tokens
            review_output_tokens += outcome.usage.output_tokens
            review_cost += outcome.usage.cost_usd
            if outcome.error or outcome.output is None:
                logger.warning("PR #%s: deep review failed for %s — %s",
                               pr_number, file_path, outcome.error)
                continue
            file_output: FileReviewOutput = outcome.output  # type: ignore[assignment]
            for comment in file_output.comments:
                all_comments.append(comment)
            per_file_findings.append(
                {
                    "file_path": file_path,
                    "comments": [c.model_dump(mode="json") for c in file_output.comments],
                }
            )
        timings["review_ms"] = int((time.monotonic() - review_step_start) * 1000)
        timings["retrieval_ms"] = retrieval_ms_total

        # ---------------- Step 3: cross-reference -----------------------------
        crossref_outcome: _StepOutcome | None = None
        if len(per_file_findings) >= 2:
            crossref_outcome = await self._run_crossref(per_file_findings)
            step_usages.append(crossref_outcome.usage)
            timings["crossref_ms"] = crossref_outcome.usage.latency_ms
            if crossref_outcome.output is not None and not crossref_outcome.error:
                xref: CrossReferenceOutput = crossref_outcome.output  # type: ignore[assignment]
                all_comments.extend(xref.comments)
        else:
            timings["crossref_ms"] = 0

        # ---------------- Step 4: synthesis ----------------------------------
        synthesis_outcome = await self._run_synthesis(
            pr_title=pr_title,
            triage_report=triage_report,
            all_comments=all_comments,
        )
        step_usages.append(synthesis_outcome.usage)
        timings["synthesis_ms"] = synthesis_outcome.usage.latency_ms
        if synthesis_outcome.error or synthesis_outcome.output is None:
            self.cost_guard.record_failure()
            return None, f"synthesis failed: {synthesis_outcome.error}"
        synthesis: ReviewSynthesis = synthesis_outcome.output  # type: ignore[assignment]

        # ---------------- Aggregate ------------------------------------------
        total_input = sum(s.input_tokens for s in step_usages)
        total_output = sum(s.output_tokens for s in step_usages)
        total_tokens = total_input + total_output
        elapsed_ms = int((time.monotonic() - start) * 1000)

        self.cost_guard.record_usage(repo_id, total_tokens)

        final_output = ReviewOutput(
            summary=synthesis.summary,
            comments=all_comments,
            pr_quality_score=synthesis.pr_quality_score,
            review_focus_areas=synthesis.review_focus_areas,
        )

        # Pick the most "expensive" step's model id as the headline model_version.
        headline_model = max(
            step_usages,
            key=lambda s: s.input_tokens + s.output_tokens,
        ).model_version

        logger.info(
            "PR #%s: review done in %sms tokens=%s comments=%s diff_hash=%s",
            pr_number,
            elapsed_ms,
            total_tokens,
            len(all_comments),
            diff_hash[:16],
        )

        return (
            OrchestratorResult(
                output=final_output,
                diff_hash=diff_hash,
                prompt_hash=prompt_hash,
                model_version=headline_model,
                total_tokens=total_tokens,
                input_tokens=total_input,
                output_tokens=total_output,
                latency_ms=elapsed_ms,
                triage_result=triage_report.model_dump(mode="json"),
                pipeline_step_timings=timings,
                step_usages=step_usages,
                retrieval_ms=retrieval_ms_total,
            ),
            None,
        )

    # ----------------------------------------------------------------- step 1

    async def _run_triage(
        self,
        parsed: ParsedDiff,
        per_file_diffs: dict[str, str],
        pr_title: str,
    ) -> _StepOutcome:
        file_summaries = [
            {
                "path": f.path,
                "status": f.status,
                "additions": f.additions,
                "deletions": f.deletions,
                "preview": (per_file_diffs.get(f.path, "") or "")[:_MAX_TRIAGE_PREVIEW_CHARS],
            }
            for f in parsed.files
        ]
        user_prompt = build_triage_user_prompt(pr_title, file_summaries)
        return await self._call_step(
            step="triage",
            system_prompt=TRIAGE_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            schema=TriageReport,
        )

    @staticmethod
    def _select_files_to_review(triage: TriageReport, parsed: ParsedDiff) -> list[str]:
        """High/medium-risk files first, in their original diff order."""
        order = {f.path: i for i, f in enumerate(parsed.files)}
        wanted: set[str] = set()
        for item in triage.files:
            if item.risk in (FileRisk.HIGH, FileRisk.MEDIUM):
                wanted.add(item.file_path)
        # Fallback: if triage marked everything skip/low, still review code-bearing files.
        if not wanted:
            wanted = {f.path for f in parsed.files if not f.path.endswith((".lock", ".md"))}
        return sorted(wanted, key=lambda p: order.get(p, len(order)))

    # ----------------------------------------------------------------- step 2

    async def _run_file_review(
        self,
        *,
        pr_title: str,
        file_path: str,
        file_diff: str,
        file_change: FileChange | None,
        repo_id: str,
    ) -> tuple[_StepOutcome, int]:
        """Run step 2 for one file. Returns ``(outcome, retrieval_ms)``."""
        diff_chunk = file_diff[:_MAX_PER_FILE_DIFF_CHARS]
        context_chunks, retrieval_ms = await self._context_for_file(
            repo_id=repo_id,
            file_path=file_path,
            file_change=file_change,
            file_diff=diff_chunk,
        )
        user_prompt = build_review_user_prompt(pr_title, diff_chunk, context_chunks, file_path=file_path)
        outcome = await self._call_step(
            step="review",
            system_prompt=REVIEW_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            schema=FileReviewOutput,
        )
        return outcome, retrieval_ms

    async def _context_for_file(
        self,
        *,
        repo_id: str,
        file_path: str,
        file_change: FileChange | None,
        file_diff: str,
    ) -> tuple[list[str], int]:
        """
        Build retrieval context for one file. Uses the hybrid retriever if wired,
        otherwise falls back to a diff-only context.
        """
        if self.retriever is not None and file_change is not None:
            try:
                result = await self.retriever.retrieve_for_file(
                    repo_id=repo_id, file=file_change, diff_text=file_diff
                )
                if result.context.text.strip():
                    return [result.context.text], result.elapsed_ms
                return [], result.elapsed_ms
            except Exception as exc:
                logger.warning("Retrieval failed for %s: %s", file_path, exc)

        # Diff-only fallback (also used by unit tests with no retriever).
        chunks: list[str] = []
        if file_diff.strip():
            chunks.append(file_diff[:_MAX_CONTEXT_CHUNK])
        return chunks[:_MAX_CONTEXT_CHUNKS], 0

    # ----------------------------------------------------------------- step 3

    async def _run_crossref(self, per_file_findings: list[dict]) -> _StepOutcome:
        user_prompt = build_crossref_user_prompt(per_file_findings)
        return await self._call_step(
            step="crossref",
            system_prompt=CROSSREF_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            schema=CrossReferenceOutput,
        )

    # ----------------------------------------------------------------- step 4

    async def _run_synthesis(
        self,
        pr_title: str,
        triage_report: TriageReport,
        all_comments: list[ReviewComment],
    ) -> _StepOutcome:
        triage_summary = {
            "total_files": triage_report.total_files,
            "files_to_review": triage_report.files_to_review,
            "high": [f.file_path for f in triage_report.files if f.risk == FileRisk.HIGH],
            "medium": [f.file_path for f in triage_report.files if f.risk == FileRisk.MEDIUM],
        }
        comments_payload = [c.model_dump(mode="json") for c in all_comments]
        user_prompt = build_synthesis_user_prompt(pr_title, triage_summary, comments_payload)
        return await self._call_step(
            step="synthesis",
            system_prompt=SYNTHESIS_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            schema=ReviewSynthesis,
        )

    # ----------------------------------------------------------------- shared

    async def _call_step(
        self,
        *,
        step: str,
        system_prompt: str,
        user_prompt: str,
        schema,
    ) -> _StepOutcome:
        """Wrap one LLM call: time it, split tokens for pricing, build a usage row."""
        started = time.monotonic()
        try:
            output, est_tokens, model_version = await self.llm_gateway.generate(
                system_prompt,
                user_prompt,
                schema,
                temperature=0.0,
            )
        except LLMGatewayError as exc:
            elapsed = int((time.monotonic() - started) * 1000)
            usage = PipelineStepUsage(
                step=step,
                model_version="mock",
                input_tokens=0,
                output_tokens=0,
                cost_usd=0.0,
                latency_ms=elapsed,
            )
            return _StepOutcome(output=None, usage=usage, error=str(exc))

        elapsed = int((time.monotonic() - started) * 1000)
        in_tok, out_tok = split_estimated_tokens(est_tokens)
        cost = estimate_llm_cost_usd(model_version, in_tok, out_tok)
        usage = PipelineStepUsage(
            step=step,
            model_version=model_version,
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_usd=cost,
            latency_ms=elapsed,
        )
        return _StepOutcome(output=output, usage=usage)

    def _split_diff_by_file(self, raw_diff: str) -> dict[str, str]:
        """Cheaply split a unified diff into per-file blobs keyed by post-rename path."""
        out: dict[str, str] = {}
        if not raw_diff.strip():
            return out
        body = raw_diff if len(raw_diff) <= _MAX_DIFF_CHARS else raw_diff[:_MAX_DIFF_CHARS]
        parts = body.split("\ndiff --git ")
        for i, part in enumerate(parts):
            piece = part if i == 0 else "diff --git " + part
            piece = piece.strip()
            if not piece:
                continue
            # First line should be `diff --git a/<path> b/<path>`
            first_line = piece.splitlines()[0]
            path = first_line.split(" b/", 1)[1].strip() if " b/" in first_line else "unknown"
            out[path] = piece
        return out

    def _estimate_tokens(self, parsed: ParsedDiff, raw_diff: str) -> int:
        """Rough token estimate for the cost-guard pre-check."""
        total_chars = sum(f.additions * 80 + f.deletions * 80 for f in parsed.files)
        diff_chars = min(len(raw_diff), _MAX_DIFF_CHARS)
        return (total_chars // 4) + (diff_chars // 4) + 2_000
