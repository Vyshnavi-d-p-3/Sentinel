"""
LLM Gateway — Claude primary, GPT-4o fallback, structured JSON → Pydantic.

When no API keys are configured (or ``llm_mock_mode`` is True), returns a
deterministic stub so the pipeline runs in CI and local dev without cloud calls.
"""

from __future__ import annotations

import logging
import re
from typing import TypeVar, Type

from pydantic import BaseModel

from app.config import settings
from app.models.review_output import CommentCategory, ReviewComment, ReviewOutput, Severity

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class LLMGatewayError(Exception):
    """Raised when all LLM providers fail after retries."""

    pass


class LLMGateway:
    MAX_RETRIES = 3

    def __init__(self) -> None:
        self._primary_model = settings.default_model
        self._fallback_model = settings.fallback_model

    def _use_mock(self) -> bool:
        if settings.llm_mock_mode:
            return True
        return not (settings.anthropic_api_key.strip() or settings.openai_api_key.strip())

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        output_schema: Type[T],
        temperature: float = 0.0,
    ) -> tuple[T, int]:
        """
        Returns parsed ``output_schema`` instance and estimated total tokens (rough).
        """
        if self._use_mock():
            raw = self._mock_json_response(user_prompt, output_schema)
            est = max(1, len(system_prompt) // 4 + len(user_prompt) // 4 + len(raw) // 4)
            return self._parse_response(raw, output_schema), est

        last_err: Exception | None = None
        for attempt in range(self.MAX_RETRIES):
            try:
                raw = await self._call_primary(system_prompt, user_prompt, temperature)
                est = max(1, len(system_prompt) // 4 + len(user_prompt) // 4 + len(raw) // 4)
                return self._parse_response(raw, output_schema), est
            except Exception as e:
                last_err = e
                logger.warning("Primary LLM attempt %s failed: %s", attempt + 1, e)

        try:
            raw = await self._call_fallback(system_prompt, user_prompt, temperature)
            est = max(1, len(system_prompt) // 4 + len(user_prompt) // 4 + len(raw) // 4)
            return self._parse_response(raw, output_schema), est
        except Exception as e:
            raise LLMGatewayError(f"All providers failed: {e}") from (last_err or e)

    async def _call_primary(self, system: str, user: str, temp: float) -> str:
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
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

        client = AsyncOpenAI(api_key=settings.openai_api_key)
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

    def _parse_response(self, raw_json: str, schema: Type[T]) -> T:
        cleaned = raw_json.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0]
        return schema.model_validate_json(cleaned)

    def _mock_json_response(self, user_prompt: str, schema: Type[T]) -> str:
        """Valid JSON for ReviewOutput; uses first file path from diff if found."""
        if schema is not ReviewOutput:
            raise NotImplementedError(f"Mock LLM only supports ReviewOutput, got {schema}")
        path = "src/example.py"
        m = re.search(r"^\+\+\+ b/(.+)$", user_prompt, re.MULTILINE)
        if m:
            path = m.group(1).strip()
        line = 1
        m2 = re.search(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", user_prompt, re.MULTILINE)
        if m2:
            try:
                line = int(m2.group(1))
            except ValueError:
                line = 1
        out = ReviewOutput(
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
        return out.model_dump_json()
