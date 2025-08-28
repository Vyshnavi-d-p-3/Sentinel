"""
HybridRetriever — top-level retrieval facade used by the orchestrator.

For each changed file:
    query = build_query_for_file(file)
    bm25_results = await BM25Retriever.search(repo_id, query)
    query_vec   = await embedder.embed_query(query)
    dense_results = await DenseRetriever.search(repo_id, query_vec)
    fused = reciprocal_rank_fusion(bm25_results, dense_results)
    boosted = apply_recency_boost(fused)
    context = ContextAssembler.assemble(diff_text, boosted)

The retriever degrades gracefully:
- If the embeddings table is empty / missing, BM25 + dense return empty lists
  and assembly falls back to diff-only context (the same behavior as before
  retrieval was wired in).
- If embedding the query fails, we still return BM25-only results.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass

from app.retrieval.bm25 import BM25Retriever
from app.retrieval.context_assembler import AssembledContext, ContextAssembler
from app.retrieval.dense import DenseRetriever
from app.retrieval.embedder import VoyageEmbedder
from app.retrieval.fusion import (
    RetrievedChunk,
    apply_recency_boost,
    reciprocal_rank_fusion,
)
from app.retrieval.query_builder import build_query_for_file
from app.services.diff_parser import FileChange

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HybridResult:
    """One retrieval round: assembled context + fused chunk list + telemetry."""

    query: str
    chunks: list[RetrievedChunk]
    context: AssembledContext
    bm25_count: int
    dense_count: int
    elapsed_ms: int


class HybridRetriever:
    """Combine BM25 + dense + RRF + recency + context assembly."""

    def __init__(
        self,
        session_factory,
        embedder: VoyageEmbedder | None = None,
        assembler: ContextAssembler | None = None,
    ) -> None:
        """``session_factory`` is a callable that returns an ``AsyncSession`` context manager."""
        self._session_factory = session_factory
        self.embedder = embedder or VoyageEmbedder()
        self.assembler = assembler or ContextAssembler()

    async def retrieve_for_file(
        self,
        repo_id: str,
        file: FileChange,
        diff_text: str,
    ) -> HybridResult:
        """Retrieve and assemble context for a single changed file."""
        started = time.monotonic()
        query = build_query_for_file(file)

        bm25_results: list[RetrievedChunk] = []
        dense_results: list[RetrievedChunk] = []

        if query:
            try:
                async with self._session_factory() as session:  # type: AsyncSession
                    bm25 = BM25Retriever(session)
                    dense = DenseRetriever(session)
                    query_vec = await self.embedder.embed_query(query)
                    bm25_task = bm25.search(repo_id, query)
                    dense_task = dense.search(repo_id, query_vec)
                    bm25_results, dense_results = await asyncio.gather(
                        bm25_task, dense_task, return_exceptions=False
                    )
            except Exception as exc:
                logger.warning("Hybrid retrieval failed for %s: %s", file.path, exc)
                bm25_results, dense_results = [], []

        fused = reciprocal_rank_fusion(bm25_results, dense_results)
        boosted = apply_recency_boost(fused)

        context = self.assembler.assemble(diff_text, boosted)
        elapsed = int((time.monotonic() - started) * 1000)
        return HybridResult(
            query=query,
            chunks=boosted,
            context=context,
            bm25_count=len(bm25_results),
            dense_count=len(dense_results),
            elapsed_ms=elapsed,
        )
