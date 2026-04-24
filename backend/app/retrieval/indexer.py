"""
EmbeddingPipeline — index a repository's source files into ``repo_embeddings``.

Flow per repo:
    files -> chunker -> Voyage embedder -> upsert into pgvector / tsvector

The upsert is keyed on ``(repo_id, file_path, chunk_type, start_line)`` so
re-indexing the same file replaces its prior chunks rather than duplicating
them. ``last_commit_at`` is recorded for the recency boost in fusion.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Mapping
from datetime import datetime

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timeutil import utc_now_naive
from app.models.database import RepoEmbedding
from app.retrieval.chunker import CodeChunk, CodeChunker
from app.retrieval.embedder import VoyageEmbedder

logger = logging.getLogger(__name__)


class EmbeddingPipeline:
    """Chunk → embed → upsert."""

    def __init__(
        self,
        chunker: CodeChunker | None = None,
        embedder: VoyageEmbedder | None = None,
    ) -> None:
        self.chunker = chunker or CodeChunker()
        self.embedder = embedder or VoyageEmbedder()

    async def embed_repo(
        self,
        session: AsyncSession,
        repo_id: uuid.UUID,
        files: Mapping[str, str],
        last_commit_at: datetime | None = None,
        replace_existing: bool = True,
    ) -> int:
        """
        Index every file in ``files`` (path → content) and return chunks stored.

        ``last_commit_at`` lets fusion recency-boost recently changed files; if
        omitted we use the current UTC time. When ``replace_existing`` is True (default),
        all prior chunks for the touched files are deleted before insert.
        """
        commit_ts = last_commit_at or utc_now_naive()

        chunks: list[CodeChunk] = []
        for path, content in files.items():
            chunks.extend(self.chunker.chunk_file(path, content))

        if not chunks:
            logger.info("No chunks produced for repo %s (empty file set)", repo_id)
            return 0

        embeddings = await self.embedder.embed_documents([c.chunk_text for c in chunks])
        if len(embeddings) != len(chunks):
            logger.error(
                "Embedding count mismatch (got %s, expected %s) — aborting upsert",
                len(embeddings),
                len(chunks),
            )
            return 0

        if replace_existing:
            await session.execute(
                delete(RepoEmbedding).where(
                    RepoEmbedding.repo_id == repo_id,
                    RepoEmbedding.file_path.in_({c.file_path for c in chunks}),
                )
            )

        rows = [
            {
                "id": uuid.uuid4(),
                "repo_id": repo_id,
                "file_path": chunk.file_path,
                "chunk_type": chunk.chunk_type,
                "chunk_text": chunk.chunk_text,
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
                "embedding": vec,
                "last_commit_at": commit_ts,
            }
            for chunk, vec in zip(chunks, embeddings, strict=False)
        ]

        # ON CONFLICT DO UPDATE handles the case where a chunk at the same
        # (repo, file, chunk_type, start_line) already exists.
        stmt = pg_insert(RepoEmbedding).values(rows)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_repo_chunk_location",
            set_={
                "chunk_text": stmt.excluded.chunk_text,
                "end_line": stmt.excluded.end_line,
                "embedding": stmt.excluded.embedding,
                "last_commit_at": stmt.excluded.last_commit_at,
                "updated_at": utc_now_naive(),
            },
        )
        await session.execute(stmt)
        await session.flush()

        logger.info("Indexed %s chunks across %s files for repo %s",
                    len(rows), len({c.file_path for c in chunks}), repo_id)
        return len(rows)
