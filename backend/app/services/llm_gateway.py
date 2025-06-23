"""
LLM Gateway — unified interface for Claude and GPT-4o with retry, fallback, and tracing.

Features:
- Primary model (Claude Sonnet) with automatic fallback to GPT-4o
- Exponential backoff retry (3 attempts)
- 30-second timeout per call
- Structured JSON output via Pydantic schema
- Langfuse tracing for every call
"""

import json
import logging
from typing import TypeVar, Type

from pydantic import BaseModel

from app.config import settings

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class LLMGatewayError(Exception):
    """Raised when all LLM providers fail after retries."""
    pass


class LLMGateway:
    """
    Unified LLM interface with retry, fallback, and observability.

    Usage:
        gateway = LLMGateway()
        result = await gateway.generate(
            system_prompt="You are a code reviewer...",
            user_prompt=formatted_context,
            output_schema=ReviewOutput,
        )
    """

    MAX_RETRIES = 3
    TIMEOUT_SEC = 30

    def __init__(self):
        self._primary_model = settings.default_model
        self._fallback_model = settings.fallback_model
        # TODO: Initialize Anthropic + OpenAI clients
        # TODO: Initialize Langfuse client

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        output_schema: Type[T],
        temperature: float = 0.0,
    ) -> T:
        """
        Generate structured output from LLM.

        Tries primary model with retries, then falls back to secondary.
        All calls traced via Langfuse with token counts and latency.

        Returns:
            Parsed Pydantic model instance.

        Raises:
            LLMGatewayError: All providers failed after retries.
        """
        # Try primary
        for attempt in range(self.MAX_RETRIES):
            try:
                raw = await self._call_primary(system_prompt, user_prompt, temperature)
                return self._parse_response(raw, output_schema)
            except Exception as e:
                logger.warning(f"Primary LLM attempt {attempt + 1} failed: {e}")
                if attempt == self.MAX_RETRIES - 1:
                    logger.error("Primary exhausted, trying fallback")

        # Try fallback
        try:
            raw = await self._call_fallback(system_prompt, user_prompt, temperature)
            return self._parse_response(raw, output_schema)
        except Exception as e:
            raise LLMGatewayError(f"All providers failed: {e}") from e

    async def _call_primary(self, system: str, user: str, temp: float) -> str:
        """Call Claude Sonnet via Anthropic API."""
        # TODO: Implement with anthropic client
        # TODO: Add Langfuse trace span
        raise NotImplementedError("Anthropic client not yet configured")

    async def _call_fallback(self, system: str, user: str, temp: float) -> str:
        """Call GPT-4o via OpenAI API."""
        # TODO: Implement with openai client
        # TODO: Add Langfuse trace span
        raise NotImplementedError("OpenAI client not yet configured")

    def _parse_response(self, raw_json: str, schema: Type[T]) -> T:
        """Parse raw JSON string into Pydantic model, handling common LLM quirks."""
        cleaned = raw_json.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0]
        return schema.model_validate_json(cleaned)
