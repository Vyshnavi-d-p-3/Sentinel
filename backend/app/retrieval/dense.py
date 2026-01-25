"""
Dense vector search via pgvector cosine similarity.

Uses IVFFlat-indexed embedding column for semantic matching.
Good at finding conceptually similar code even with different naming.
"""

import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.retrieval.fusion import RetrievedChunk

logger = logging.getLogger(__name__)


class DenseRetriever:
    """Semantic search using pgvector cosine similarity."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def search(
        self, repo_id: str, query_embedding: list[float], top_k: int = 20
    ) -> list[RetrievedChunk]:
        """
        Run cosine similarity search against pgvector embeddings.

        Requires the query to already be embedded via the same model
        (text-embedding-3-small, 1536 dimensions).
        """
        sql = text("""
            SELECT id::text, file_path, chunk_text, start_line, end_line,
                   1 - (embedding <=> :query_vec::vector) AS similarity
            FROM repo_embeddings
            WHERE repo_id = :repo_id
            ORDER BY embedding <=> :query_vec::vector
            LIMIT :top_k
        """)

        result = await self.session.execute(
            sql, {
                "repo_id": repo_id,
                "query_vec": str(query_embedding),
                "top_k": top_k,
            }
        )

        return [
            RetrievedChunk(
                chunk_id=row.id,
                file_path=row.file_path,
                chunk_text=row.chunk_text,
                start_line=row.start_line,
                end_line=row.end_line,
                score=float(row.similarity),
            )
            for row in result.fetchall()
        ]
