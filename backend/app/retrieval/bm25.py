"""
BM25-equivalent full-text search via PostgreSQL ``tsvector``.

Uses the GIN-indexed ``ts_content`` column on ``repo_embeddings`` for fast
lexical matching. This is what catches exact identifier matches (function
names, error codes) that dense embeddings frequently miss.
"""

from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.retrieval.fusion import RetrievedChunk

logger = logging.getLogger(__name__)


class BM25Retriever:
    """Full-text search using PostgreSQL ``ts_rank_cd`` over ``ts_content``."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def search(
        self, repo_id: str, query: str, top_k: int | None = None
    ) -> list[RetrievedChunk]:
        """Return the top ``top_k`` chunks ranked by ``ts_rank_cd``."""
        if not query or not query.strip():
            return []
        limit = settings.retrieval_per_source_top_k if top_k is None else top_k

        sql = text(
            """
            SELECT id::text AS id,
                   file_path,
                   chunk_text,
                   start_line,
                   end_line,
                   last_commit_at,
                   ts_rank_cd(ts_content, websearch_to_tsquery('english', :query)) AS rank
            FROM repo_embeddings
            WHERE repo_id = :repo_id
              AND ts_content @@ websearch_to_tsquery('english', :query)
            ORDER BY rank DESC
            LIMIT :limit
            """
        )

        try:
            result = await self.session.execute(
                sql, {"repo_id": repo_id, "query": query, "limit": limit}
            )
        except Exception as exc:
            # Most commonly this is "table does not exist" before indexing has run.
            logger.debug("BM25 search failed for repo %s: %s", repo_id, exc)
            return []

        return [
            RetrievedChunk(
                chunk_id=row.id,
                file_path=row.file_path,
                chunk_text=row.chunk_text,
                start_line=row.start_line,
                end_line=row.end_line,
                score=float(row.rank),
                last_commit_at=row.last_commit_at,
            )
            for row in result.fetchall()
        ]
