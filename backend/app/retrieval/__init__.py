"""
Retrieval subsystem.

Public surface:

- ``CodeChunker``           — language-aware file chunking
- ``VoyageEmbedder``        — Voyage AI embeddings (with deterministic mock)
- ``EmbeddingPipeline``     — chunk → embed → upsert into ``repo_embeddings``
- ``BM25Retriever``         — full-text search via PostgreSQL ``tsvector``
- ``DenseRetriever``        — cosine search via pgvector
- ``RetrievedChunk``        — common return type
- ``reciprocal_rank_fusion``/``apply_recency_boost`` — fusion primitives
- ``ContextAssembler``      — token-budgeted prompt context
- ``HybridRetriever``       — top-level retrieval facade
- ``build_query_for_file``  — diff-aware query construction
- ``walk_repo``             — operator-side walker for the indexing CLI
"""

from app.retrieval.bm25 import BM25Retriever
from app.retrieval.chunker import CodeChunk, CodeChunker
from app.retrieval.context_assembler import AssembledContext, ContextAssembler
from app.retrieval.dense import DenseRetriever
from app.retrieval.embedder import VoyageEmbedder
from app.retrieval.fusion import (
    RetrievedChunk,
    apply_recency_boost,
    reciprocal_rank_fusion,
)
from app.retrieval.hybrid import HybridResult, HybridRetriever
from app.retrieval.indexer import EmbeddingPipeline
from app.retrieval.query_builder import build_query_for_file
from app.retrieval.repo_walker import (
    DEFAULT_MAX_BYTES,
    DEFAULT_MAX_FILES,
    WalkStats,
    walk_repo,
)

__all__ = [
    "AssembledContext",
    "BM25Retriever",
    "CodeChunk",
    "CodeChunker",
    "ContextAssembler",
    "DEFAULT_MAX_BYTES",
    "DEFAULT_MAX_FILES",
    "DenseRetriever",
    "EmbeddingPipeline",
    "HybridResult",
    "HybridRetriever",
    "RetrievedChunk",
    "VoyageEmbedder",
    "WalkStats",
    "apply_recency_boost",
    "build_query_for_file",
    "reciprocal_rank_fusion",
    "walk_repo",
]
