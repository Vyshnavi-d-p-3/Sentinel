"""
BM25 full-text search via PostgreSQL tsvector.

Uses the GIN-indexed tsvector column on repo_embeddings for fast lexical matching.
Good at finding exact identifiers, function names, and error messages.
"""

import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.retrieval.fusion import RetrievedChunk

logger = logging.getLogger(__name__)


class BM25Retriever:
    """Full-text search using PostgreSQL tsvector + ts_rank_cd."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def search(
        self, repo_id: str, query: str, top_k: int = 20
    ) -> list[RetrievedChunk]:
        """
        Run BM25-equivalent search against repo_embeddings.

        Uses ts_rank_cd (cover density ranking) for better relevance
        than basic ts_rank on code content.
        """
        sql = text("""
            SELECT id::text, file_path, chunk_text, start_line, end_line,
                   ts_rank_cd(ts_content, websearch_to_tsquery('english', :query)) AS rank
            FROM repo_embeddings
            WHERE repo_id = :repo_id
              AND ts_content @@ websearch_to_tsquery('english', :query)
            ORDER BY rank DESC
            LIMIT :top_k
        """)

        result = await self.session.execute(
            sql, {"repo_id": repo_id, "query": query, "top_k": top_k}
        )

        return [
            RetrievedChunk(
                chunk_id=row.id,
                file_path=row.file_path,
                chunk_text=row.chunk_text,
                start_line=row.start_line,
                end_line=row.end_line,
                score=float(row.rank),
            )
            for row in result.fetchall()
        ]
