"""
Code chunking and embedding pipeline.

Splits repository code into function/class-level chunks, generates
embeddings via OpenAI text-embedding-3-small, and upserts to pgvector.
"""

import logging

logger = logging.getLogger(__name__)


class CodeChunker:
    """Split source files into meaningful chunks (function, class, module)."""

    MAX_CHUNK_TOKENS = 512

    def chunk_file(self, file_path: str, content: str) -> list[dict]:
        """
        Split a file into chunks. Strategy depends on language:
        - Python: split by top-level def/class
        - JS/TS: split by function/class declarations
        - Other: split by blank-line-separated blocks
        """
        # TODO: implement language-aware chunking
        # For now, chunk by ~50 line blocks
        lines = content.splitlines()
        chunks = []
        for i in range(0, len(lines), 50):
            block = lines[i:i + 50]
            chunks.append({
                "file_path": file_path,
                "chunk_type": "block",
                "chunk_text": "\n".join(block),
                "start_line": i + 1,
                "end_line": min(i + 50, len(lines)),
            })
        return chunks


class EmbeddingPipeline:
    """Generate and store embeddings for code chunks."""

    def __init__(self):
        self.chunker = CodeChunker()
        # TODO: Initialize OpenAI client

    async def embed_repo(self, repo_id: str, files: dict[str, str]) -> int:
        """
        Embed all files in a repository. Returns count of chunks stored.

        Flow: files → chunk → embed → upsert to pgvector
        """
        total = 0
        for path, content in files.items():
            chunks = self.chunker.chunk_file(path, content)
            # TODO: batch embed via OpenAI
            # TODO: upsert to repo_embeddings table
            total += len(chunks)

        logger.info(f"Embedded {total} chunks for repo {repo_id}")
        return total
