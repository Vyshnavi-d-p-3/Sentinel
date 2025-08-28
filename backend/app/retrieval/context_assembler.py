"""
Context assembler — turn (diff, retrieved chunks) into a token-budgeted string
that the per-file deep-review prompt can append directly.

Layout:
    ## Diff
    ```diff
    <diff body, capped at retrieval_diff_share of the budget>
    ```

    ## Retrieved context
    ### file/path.py:start-end (chunk_type, score=0.123)
    <chunk text>
    ...

Token counting uses ``tiktoken`` if installed; otherwise we fall back to a
4-chars-per-token heuristic (good enough for budgeting, since the LLM gateway
also has its own hard cap).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.config import settings
from app.retrieval.fusion import RetrievedChunk

logger = logging.getLogger(__name__)


def _count_tokens(text: str) -> int:
    """Best-effort token count. Falls back to chars/4 when tiktoken is unavailable."""
    if not text:
        return 0
    try:
        import tiktoken

        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        return max(1, len(text) // 4)


@dataclass(frozen=True)
class AssembledContext:
    """Output of the assembler — string + accounting."""

    text: str
    diff_tokens: int
    chunk_tokens: int
    chunks_included: int
    chunks_truncated: int
    total_tokens: int


class ContextAssembler:
    """Produce a token-budgeted context string for one file."""

    def __init__(
        self,
        token_budget: int | None = None,
        diff_share: float | None = None,
    ) -> None:
        self.token_budget = (
            settings.retrieval_context_token_budget if token_budget is None else token_budget
        )
        self.diff_share = settings.retrieval_diff_share if diff_share is None else diff_share

    def assemble(
        self,
        diff_text: str,
        chunks: list[RetrievedChunk],
    ) -> AssembledContext:
        diff_section, diff_tokens = self._build_diff_section(diff_text)
        remaining = max(self.token_budget - diff_tokens, 0)

        chunk_section, chunk_tokens, included, truncated = self._build_chunk_section(
            chunks, remaining
        )

        parts: list[str] = []
        if diff_section:
            parts.append(diff_section)
        if chunk_section:
            parts.append(chunk_section)
        body = "\n\n".join(parts)
        return AssembledContext(
            text=body,
            diff_tokens=diff_tokens,
            chunk_tokens=chunk_tokens,
            chunks_included=included,
            chunks_truncated=truncated,
            total_tokens=diff_tokens + chunk_tokens,
        )

    # ---------------------------------------------------------------- diff

    def _build_diff_section(self, diff_text: str) -> tuple[str, int]:
        if not diff_text or not diff_text.strip():
            return "", 0
        diff_budget = max(int(self.token_budget * self.diff_share), 200)

        body = diff_text
        token_count = _count_tokens(body)
        if token_count > diff_budget:
            # Linear truncation by char ratio is plenty here; the LLM only sees
            # this for context and the orchestrator caps per-file diff size.
            ratio = diff_budget / max(token_count, 1)
            cutoff = max(int(len(body) * ratio), 1)
            body = body[:cutoff] + "\n... [diff truncated for context budget]\n"
            token_count = _count_tokens(body)

        section = "## Diff\n```diff\n" + body + "\n```"
        return section, _count_tokens(section)

    # -------------------------------------------------------------- chunks

    def _build_chunk_section(
        self,
        chunks: list[RetrievedChunk],
        budget: int,
    ) -> tuple[str, int, int, int]:
        if not chunks or budget <= 0:
            return "", 0, 0, 0

        header = "## Retrieved context"
        running_tokens = _count_tokens(header)
        body_parts: list[str] = [header]
        included = 0
        truncated = 0

        # Highest-scored first (RRF / recency-boosted).
        ordered = sorted(chunks, key=lambda c: c.score, reverse=True)

        for chunk in ordered:
            chunk_block = self._format_chunk(chunk)
            chunk_tokens = _count_tokens(chunk_block)
            if running_tokens + chunk_tokens <= budget:
                body_parts.append(chunk_block)
                running_tokens += chunk_tokens
                included += 1
                continue

            # Try to fit a truncated version if it would otherwise be skipped.
            remaining = budget - running_tokens
            if remaining < 200:
                truncated += 1
                continue
            shrunk = self._truncate_chunk(chunk, remaining)
            body_parts.append(shrunk)
            running_tokens += _count_tokens(shrunk)
            included += 1
            truncated += 1
            break  # subsequent chunks won't fit

        return "\n\n".join(body_parts), running_tokens, included, truncated

    @staticmethod
    def _format_chunk(chunk: RetrievedChunk) -> str:
        location = chunk.file_path
        if chunk.start_line is not None and chunk.end_line is not None:
            location = f"{chunk.file_path}:{chunk.start_line}-{chunk.end_line}"
        score_str = f"score={chunk.score:.3f}"
        header = f"### {location} ({score_str})"
        return f"{header}\n```\n{chunk.chunk_text}\n```"

    @staticmethod
    def _truncate_chunk(chunk: RetrievedChunk, token_budget: int) -> str:
        char_budget = max(token_budget * 4 - 80, 200)  # leave room for the heading
        body = chunk.chunk_text[:char_budget] + "\n... [chunk truncated]"
        location = chunk.file_path
        if chunk.start_line is not None and chunk.end_line is not None:
            location = f"{chunk.file_path}:{chunk.start_line}-{chunk.end_line}"
        return f"### {location} (score={chunk.score:.3f})\n```\n{body}\n```"
