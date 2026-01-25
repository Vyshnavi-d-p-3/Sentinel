"""
Reciprocal Rank Fusion — merges ranked lists from BM25 and dense retrieval.

RRF score = Σ 1/(k + rank_i) for each retrieval source.
Default k=60 (Cormack et al., 2009).
"""

from dataclasses import dataclass


@dataclass
class RetrievedChunk:
    """A code chunk returned by a retrieval source."""
    chunk_id: str
    file_path: str
    chunk_text: str
    start_line: int | None = None
    end_line: int | None = None
    score: float = 0.0


def reciprocal_rank_fusion(
    *ranked_lists: list[RetrievedChunk],
    k: int = 60,
    top_n: int = 5,
) -> list[RetrievedChunk]:
    """
    Merge multiple ranked lists using Reciprocal Rank Fusion.

    Args:
        *ranked_lists: Ranked result lists from different retrievers.
        k: Smoothing constant (higher → less impact from top ranks).
        top_n: Number of results to return.

    Returns:
        Top-N chunks sorted by fused RRF score descending.
    """
    scores: dict[str, float] = {}
    chunks: dict[str, RetrievedChunk] = {}

    for ranked_list in ranked_lists:
        for rank, chunk in enumerate(ranked_list, start=1):
            rrf_score = 1.0 / (k + rank)
            scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + rrf_score
            chunks[chunk.chunk_id] = chunk

    top_ids = sorted(scores, key=lambda cid: scores[cid], reverse=True)[:top_n]

    result = []
    for chunk_id in top_ids:
        chunk = chunks[chunk_id]
        chunk.score = scores[chunk_id]
        result.append(chunk)

    return result
