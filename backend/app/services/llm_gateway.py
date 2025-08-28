"""
LLM Gateway — Claude primary, GPT-4o fallback, structured JSON → Pydantic.

When no API keys are configured (or ``llm_mock_mode`` is True), returns a
deterministic stub so the pipeline runs in CI and local dev without cloud calls.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import TypeVar

from pydantic import BaseModel

from app.config import settings
from app.models.review_output import (
    CommentCategory,
    CrossReferenceOutput,
    FileReviewOutput,
    FileRisk,
    FileTriageItem,
    ReviewComment,
    ReviewOutput,
    ReviewSynthesis,
    Severity,
    TriageReport,
)

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class LLMGatewayError(Exception):
    """Raised when all LLM providers fail after retries."""

    pass


# Hard caps on prompt size — keeps a runaway upstream from feeding us a 10 MB
# diff that would blow our token budget and provider limits in one shot.
_MAX_SYSTEM_PROMPT_CHARS = 32_000
_MAX_USER_PROMPT_CHARS = 200_000


class LLMGateway:
    MAX_RETRIES = 3

    def __init__(self) -> None:
        self._primary_model = settings.default_model
        self._fallback_model = settings.fallback_model
        self._timeout = float(getattr(settings, "llm_call_timeout_sec", 60.0))

    def _use_mock(self) -> bool:
        if settings.llm_mock_mode:
            return True
        return not (settings.anthropic_api_key.strip() or settings.openai_api_key.strip())

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        output_schema: type[T],
        temperature: float = 0.0,
    ) -> tuple[T, int, str]:
        """
        Returns parsed ``output_schema`` instance, estimated total tokens (rough), and model id.
        """
        # Defensive truncation — prompts that come in larger than these caps
        # are almost certainly a bug or an attack. We trim rather than reject
        # because the orchestrator already pre-bounds these in normal flow.
        if len(system_prompt) > _MAX_SYSTEM_PROMPT_CHARS:
            logger.warning(
                "System prompt truncated from %s to %s chars",
                len(system_prompt),
                _MAX_SYSTEM_PROMPT_CHARS,
            )
            system_prompt = system_prompt[:_MAX_SYSTEM_PROMPT_CHARS]
        if len(user_prompt) > _MAX_USER_PROMPT_CHARS:
            logger.warning(
                "User prompt truncated from %s to %s chars",
                len(user_prompt),
                _MAX_USER_PROMPT_CHARS,
            )
            user_prompt = user_prompt[:_MAX_USER_PROMPT_CHARS]

        if self._use_mock():
            raw = self._mock_json_response(user_prompt, output_schema)
            est = max(1, len(system_prompt) // 4 + len(user_prompt) // 4 + len(raw) // 4)
            return self._parse_response(raw, output_schema), est, "mock"

        last_err: Exception | None = None
        for attempt in range(self.MAX_RETRIES):
            try:
                raw = await asyncio.wait_for(
                    self._call_primary(system_prompt, user_prompt, temperature),
                    timeout=self._timeout,
                )
                est = max(1, len(system_prompt) // 4 + len(user_prompt) // 4 + len(raw) // 4)
                return self._parse_response(raw, output_schema), est, self._primary_model
            except TimeoutError as e:
                last_err = e
                logger.warning("Primary LLM attempt %s timed out after %ss", attempt + 1, self._timeout)
            except Exception as e:
                last_err = e
                logger.warning("Primary LLM attempt %s failed: %s", attempt + 1, e)

        try:
            raw = await asyncio.wait_for(
                self._call_fallback(system_prompt, user_prompt, temperature),
                timeout=self._timeout,
            )
            est = max(1, len(system_prompt) // 4 + len(user_prompt) // 4 + len(raw) // 4)
            return self._parse_response(raw, output_schema), est, self._fallback_model
        except Exception as e:
            raise LLMGatewayError(f"All providers failed: {e}") from (last_err or e)

    async def _call_primary(self, system: str, user: str, temp: float) -> str:
        import anthropic

        client = anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            timeout=self._timeout,
        )
        msg = await client.messages.create(
            model=self._primary_model,
            max_tokens=8192,
            temperature=temp,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        block = msg.content[0]
        if block.type != "text":
            raise RuntimeError(f"Unexpected Anthropic block type: {block.type}")
        return block.text

    async def _call_fallback(self, system: str, user: str, temp: float) -> str:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=self._timeout)
        resp = await client.chat.completions.create(
            model=self._fallback_model,
            temperature=temp,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        choice = resp.choices[0].message.content
        if not choice:
            raise RuntimeError("OpenAI returned empty content")
        return choice

    def _parse_response(self, raw_json: str, schema: type[T]) -> T:
        cleaned = raw_json.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0]
        return schema.model_validate_json(cleaned)

    def _mock_json_response(self, user_prompt: str, schema: type[T]) -> str:
        """Deterministic stub output for every schema the pipeline emits."""
        if schema is ReviewOutput:
            return self._mock_review_output(user_prompt).model_dump_json()
        if schema is FileReviewOutput:
            return self._mock_file_review(user_prompt).model_dump_json()
        if schema is TriageReport:
            return self._mock_triage(user_prompt).model_dump_json()
        if schema is CrossReferenceOutput:
            return CrossReferenceOutput(comments=[]).model_dump_json()
        if schema is ReviewSynthesis:
            return self._mock_synthesis(user_prompt).model_dump_json()
        raise NotImplementedError(f"Mock LLM has no stub for schema {schema}")

    @staticmethod
    def _first_file_from_diff(text: str) -> tuple[str, int]:
        """Best-effort extraction of (file_path, first_changed_line) from a diff blob."""
        path = "src/example.py"
        m = re.search(r"^\+\+\+ b/(.+)$", text, re.MULTILINE)
        if m:
            path = m.group(1).strip()
        line = 1
        m2 = re.search(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", text, re.MULTILINE)
        if m2:
            try:
                line = int(m2.group(1))
            except ValueError:
                line = 1
        return path, line

    def _mock_review_output(self, user_prompt: str) -> ReviewOutput:
        path, line = self._first_file_from_diff(user_prompt)
        return ReviewOutput(
            summary=(
                f"Mock review (no LLM keys configured): scanned `{path}`. "
                "Replace stub output by setting ANTHROPIC_API_KEY or OPENAI_API_KEY."
            ),
            comments=[
                ReviewComment(
                    file_path=path,
                    line_number=line,
                    category=CommentCategory.SUGGESTION,
                    severity=Severity.LOW,
                    title="Verify behavior against requirements",
                    body=(
                        "This is deterministic scaffold output. "
                        "Wire real LLM keys to generate actionable review comments."
                    ),
                    suggestion="Run with API keys and re-check findings.",
                    confidence=0.3,
                )
            ],
            pr_quality_score=7.0,
            review_focus_areas=["Correctness", "Security", "Tests"],
        )

    def _mock_file_review(self, user_prompt: str) -> FileReviewOutput:
        path, line = self._first_file_from_diff(user_prompt)
        m = re.search(r"^## File under review\n(.+)$", user_prompt, re.MULTILINE)
        if m:
            path = m.group(1).strip() or path
        return FileReviewOutput(
            file_path=path,
            comments=[
                ReviewComment(
                    file_path=path,
                    line_number=line,
                    category=CommentCategory.SUGGESTION,
                    severity=Severity.LOW,
                    title=f"Mock review for {path}",
                    body="Deterministic stub output from the mock LLM gateway.",
                    suggestion=None,
                    confidence=0.3,
                )
            ],
        )

    def _mock_triage(self, user_prompt: str) -> TriageReport:
        """Triage every file mentioned in the JSON payload as ``medium`` risk."""
        files: list[FileTriageItem] = []
        try:
            import json as _json

            start = user_prompt.find("{")
            payload = _json.loads(user_prompt[start:]) if start >= 0 else {}
            for f in payload.get("files", []):
                if not isinstance(f, dict):
                    continue
                files.append(
                    FileTriageItem(
                        file_path=str(f.get("path") or f.get("file_path") or "unknown"),
                        risk=FileRisk.MEDIUM,
                        reasoning="Mock triage: deterministic medium risk for every file.",
                        lines_changed=int(f.get("additions", 0)) + int(f.get("deletions", 0)),
                    )
                )
        except Exception:  # noqa: S110 — mock path, swallow malformed prompts intentionally
            logger.debug("Mock triage failed to parse prompt; returning empty triage")
        return TriageReport(
            files=files,
            total_files=len(files),
            files_to_review=len(files),
        )

    def _mock_synthesis(self, user_prompt: str) -> ReviewSynthesis:
        return ReviewSynthesis(
            summary=(
                "Mock synthesis: pipeline ran in deterministic mode without an LLM provider. "
                "Set ANTHROPIC_API_KEY or OPENAI_API_KEY to produce real summaries."
            ),
            pr_quality_score=7.0,
            review_focus_areas=["Correctness", "Security", "Tests"],
        )
