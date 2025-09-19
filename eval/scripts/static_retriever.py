"""
Static context retriever for the eval ablation harness.

This is a drop-in shim for ``HybridRetriever`` that returns fixture-provided
context chunks instead of querying the live ``repo_embeddings`` table. It lets
the ablation runner exercise the orchestrator's "with retrieval" code path
deterministically — no Postgres, no pgvector, no Voyage API key.

Per fixture, the JSON may include::

    "context_files": {
        "src/auth/session.py": [
            "def make_session(...): ...",
            "SESSION_TTL = 3600  # documented contract"
        ]
    }

Each list entry becomes one chunk in the assembled context. When the
orchestrator asks for context for a file path that's missing from this map,
the retriever returns an empty result (so behaviour matches a cache miss
in production).
"""

from __future__ import annotations

import time
from typing import Mapping, Sequence

from app.retrieval.context_assembler import AssembledContext
from app.retrieval.fusion import RetrievedChunk
from app.retrieval.hybrid import HybridResult
from app.services.diff_parser import FileChange


def _approx_tokens(text: str) -> int:
    """Char/4 heuristic — matches the assembler's tiktoken-free fallback."""
    return max(1, len(text) // 4)


class StaticContextRetriever:
    """
    Mimic ``HybridRetriever`` for ablation runs.

    The orchestrator only calls ``retrieve_for_file`` and reads
    ``result.context.text`` / ``result.elapsed_ms``, so a minimal stub is
    sufficient — we don't need to implement RRF or recency.
    """

    def __init__(self, context_by_file: Mapping[str, Sequence[str]]) -> None:
        self._context_by_file = {path: list(chunks) for path, chunks in context_by_file.items()}

    async def retrieve_for_file(
        self,
        repo_id: str,
        file: FileChange,
        diff_text: str,
    ) -> HybridResult:
        started = time.monotonic()
        chunks_text = self._context_by_file.get(file.path, [])

        # Build a synthetic AssembledContext so the orchestrator can splice it
        # into the prompt verbatim. We mirror HybridRetriever's "diff first,
        # context after" layout for cross-config comparability.
        sections: list[str] = []
        if diff_text.strip():
            sections.append(f"# DIFF\n{diff_text}")
        for idx, chunk in enumerate(chunks_text, start=1):
            sections.append(f"# CONTEXT {idx} :: {file.path}\n{chunk}")
        text = "\n\n".join(sections).strip()

        diff_tokens = _approx_tokens(diff_text) if diff_text.strip() else 0
        chunk_tokens = sum(_approx_tokens(c) for c in chunks_text)

        retrieved_chunks = [
            RetrievedChunk(
                chunk_id=f"static-{file.path}-{idx}",
                file_path=file.path,
                chunk_text=chunk,
                start_line=0,
                end_line=0,
                score=1.0 / (idx + 1),  # rank-decaying score so order is preserved
            )
            for idx, chunk in enumerate(chunks_text)
        ]

        context = AssembledContext(
            text=text,
            diff_tokens=diff_tokens,
            chunk_tokens=chunk_tokens,
            chunks_included=len(chunks_text),
            chunks_truncated=0,
            total_tokens=diff_tokens + chunk_tokens,
        )
        elapsed = int((time.monotonic() - started) * 1000)
        return HybridResult(
            query=file.path,
            chunks=retrieved_chunks,
            context=context,
            bm25_count=0,
            dense_count=len(chunks_text),
            elapsed_ms=elapsed,
        )
