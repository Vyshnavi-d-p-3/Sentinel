"""
Reciprocal Rank Fusion + recency boost.

RRF score for a chunk that appears at rank ``r_i`` in source ``i`` is:

    score(d) = Σ 1 / (k + r_i)

with the standard ``k = 60`` (Cormack et al., 2009).

Sentinel additionally adds an exponentially-decaying additive *recency boost*
(0 → ``RECENCY_BOOST_MAX``) so chunks from recently changed files outrank
equally-relevant chunks from years-old code. The boost is computed from each
chunk's ``last_commit_at`` timestamp.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.config import settings


@dataclass
class RetrievedChunk:
    """A code chunk returned by a retrieval source."""

    chunk_id: str
    file_path: str
    chunk_text: str
    start_line: int | None = None
    end_line: int | None = None
    score: float = 0.0
    last_commit_at: datetime | None = None


def reciprocal_rank_fusion(
    *ranked_lists: list[RetrievedChunk],
    k: int | None = None,
    top_n: int | None = None,
) -> list[RetrievedChunk]:
    """
    Merge multiple ranked lists using Reciprocal Rank Fusion.

    Defaults read from settings (``rrf_k`` and ``retrieval_top_k``) so callers
    do not need to thread tuning parameters everywhere.
    """
    k_value = settings.rrf_k if k is None else k
    n_value = settings.retrieval_top_k if top_n is None else top_n

    scores: dict[str, float] = {}
    chunks: dict[str, RetrievedChunk] = {}

    for ranked_list in ranked_lists:
        for rank, chunk in enumerate(ranked_list, start=1):
            rrf_score = 1.0 / (k_value + rank)
            scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + rrf_score
            chunks[chunk.chunk_id] = chunk

    top_ids = sorted(scores, key=lambda cid: scores[cid], reverse=True)[:n_value]

    result: list[RetrievedChunk] = []
    for chunk_id in top_ids:
        chunk = chunks[chunk_id]
        chunk.score = scores[chunk_id]
        result.append(chunk)
    return result


def apply_recency_boost(
    chunks: list[RetrievedChunk],
    *,
    now: datetime | None = None,
    boost_max: float | None = None,
    half_life_days: int | None = None,
) -> list[RetrievedChunk]:
    """
    Re-score ``chunks`` in place with an additive exponential recency boost.

    For a chunk last touched ``d`` days ago:

        boost = boost_max * exp(-d / half_life_days)

    Chunks without ``last_commit_at`` get no boost. Returns the list re-sorted
    by the new score, preserving the input order on ties.
    """
    boost_cap = settings.retrieval_recency_boost_max if boost_max is None else boost_max
    half_life = (
        settings.retrieval_recency_half_life_days if half_life_days is None else half_life_days
    )
    if boost_cap <= 0 or half_life <= 0:
        return chunks

    current_time = now or datetime.utcnow()

    for chunk in chunks:
        if chunk.last_commit_at is None:
            continue
        age: timedelta = current_time - chunk.last_commit_at
        days = max(age.total_seconds() / 86_400, 0.0)
        boost = boost_cap * math.exp(-days / half_life)
        chunk.score += boost

    chunks.sort(key=lambda c: c.score, reverse=True)
    return chunks
