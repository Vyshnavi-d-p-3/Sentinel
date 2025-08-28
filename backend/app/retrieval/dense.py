"""
Dense vector search via pgvector cosine similarity.

Uses the IVFFlat-indexed ``embedding`` column on ``repo_embeddings`` for fast
approximate nearest-neighbor search. The query embedding must come from the
same model as the stored vectors (Voyage AI ``voyage-code-3``, dim 1024).
"""

from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.retrieval.fusion import RetrievedChunk

logger = logging.getLogger(__name__)


class DenseRetriever:
    """Semantic search using pgvector cosine similarity."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def search(
        self,
        repo_id: str,
        query_embedding: list[float],
        top_k: int | None = None,
    ) -> list[RetrievedChunk]:
        """Return top ``top_k`` chunks by cosine similarity to ``query_embedding``."""
        if not query_embedding:
            return []
        limit = settings.retrieval_per_source_top_k if top_k is None else top_k

        # pgvector requires a literal vector text; render as ``[v1, v2, ...]``.
        vec_literal = "[" + ",".join(f"{v:.6f}" for v in query_embedding) + "]"

        sql = text(
            """
            SELECT id::text AS id,
                   file_path,
                   chunk_text,
                   start_line,
                   end_line,
                   last_commit_at,
                   1 - (embedding <=> CAST(:query_vec AS vector)) AS similarity
            FROM repo_embeddings
            WHERE repo_id = :repo_id
              AND embedding IS NOT NULL
            ORDER BY embedding <=> CAST(:query_vec AS vector)
            LIMIT :limit
            """
        )

        try:
            result = await self.session.execute(
                sql,
                {"repo_id": repo_id, "query_vec": vec_literal, "limit": limit},
            )
        except Exception as exc:
            logger.debug("Dense search failed for repo %s: %s", repo_id, exc)
            return []

        return [
            RetrievedChunk(
                chunk_id=row.id,
                file_path=row.file_path,
                chunk_text=row.chunk_text,
                start_line=row.start_line,
                end_line=row.end_line,
                score=float(row.similarity),
                last_commit_at=row.last_commit_at,
            )
            for row in result.fetchall()
        ]
