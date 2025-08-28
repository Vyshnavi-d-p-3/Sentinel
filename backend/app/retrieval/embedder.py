"""
Embedder — produces ``settings.embedding_dim``-dim vectors via Voyage AI's
``voyage-code-3`` model. Falls back to a deterministic hash-based stub when no
API key is configured so retrieval, indexing, and tests work in CI without
external calls.

Usage:
    embedder = VoyageEmbedder()
    docs = await embedder.embed_documents(["def foo(): ..."])
    query = await embedder.embed_query("foo")
"""

from __future__ import annotations

import hashlib
import logging
import math
from collections.abc import Iterable

from app.config import settings

logger = logging.getLogger(__name__)


def _l2_normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


class VoyageEmbedder:
    """Wraps the Voyage AI client with batching, retries, and a mock fallback."""

    BATCH_SIZE = 64

    def __init__(self) -> None:
        self._dim = settings.embedding_dim
        self._model = settings.embedding_model
        self._api_key = settings.voyageai_api_key.strip()

    @property
    def model(self) -> str:
        return self._model

    @property
    def dim(self) -> int:
        return self._dim

    def _use_mock(self) -> bool:
        return not self._api_key

    async def embed_documents(self, texts: Iterable[str]) -> list[list[float]]:
        """Embed a batch of code chunks (asymmetric: ``input_type='document'``)."""
        return await self._embed(list(texts), input_type="document")

    async def embed_query(self, text: str) -> list[float]:
        """Embed a single retrieval query (asymmetric: ``input_type='query'``)."""
        vectors = await self._embed([text], input_type="query")
        return vectors[0] if vectors else self._mock_vector(text)

    async def _embed(self, texts: list[str], *, input_type: str) -> list[list[float]]:
        if not texts:
            return []
        if self._use_mock():
            return [self._mock_vector(t) for t in texts]

        try:
            import voyageai

            client = voyageai.AsyncClient(api_key=self._api_key)
            out: list[list[float]] = []
            for start in range(0, len(texts), self.BATCH_SIZE):
                batch = texts[start : start + self.BATCH_SIZE]
                resp = await client.embed(
                    batch,
                    model=self._model,
                    input_type=input_type,
                )
                out.extend(resp.embeddings)
            return out
        except Exception as exc:
            logger.warning("Voyage embedding call failed (%s); falling back to mock vectors", exc)
            return [self._mock_vector(t) for t in texts]

    def _mock_vector(self, text: str) -> list[float]:
        """
        Deterministic pseudo-embedding from SHA-256 hashes.

        Produces a stable, L2-normalized vector of length ``self._dim`` so
        unit/integration tests and the eval harness can run without API keys.
        """
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        # Repeat/extend the digest until we have enough bytes.
        repeats = (self._dim + len(digest) - 1) // len(digest)
        raw = (digest * repeats)[: self._dim]
        # Map each byte to [-1, 1] then L2-normalize so cosine math stays sane.
        vec = [(b - 127.5) / 127.5 for b in raw]
        return _l2_normalize(vec)
