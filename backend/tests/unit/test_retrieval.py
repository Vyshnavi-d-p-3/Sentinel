"""Unit tests for the retrieval subsystem (no DB required)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from app.retrieval.chunker import CodeChunker
from app.retrieval.context_assembler import ContextAssembler
from app.retrieval.embedder import VoyageEmbedder
from app.retrieval.fusion import (
    RetrievedChunk,
    apply_recency_boost,
    reciprocal_rank_fusion,
)
from app.retrieval.query_builder import build_query_for_file
from app.services.diff_parser import FileChange

# ---------------------------------------------------------------------------
# Chunker
# ---------------------------------------------------------------------------

PY_FILE = '''"""Module docstring."""

import os

CONST = 1


def alpha(x):
    return x + 1


class Beta:
    def method(self):
        return 2


async def gamma():
    return 3
'''

JS_FILE = """import x from 'x';

export function alpha(a) {
  return a;
}

export class Beta {
  do() { return 1; }
}

const gamma = async () => 2;
"""


def test_chunker_python_emits_module_plus_top_level_defs():
    chunks = CodeChunker().chunk_file("src/foo.py", PY_FILE)
    types = [c.chunk_type for c in chunks]
    assert types[0] == "module"
    assert "function" in types
    assert "class" in types
    # Function chunk text should include the top-level def line.
    fn_chunk = next(c for c in chunks if c.chunk_type == "function" and "alpha" in c.chunk_text)
    assert fn_chunk.start_line >= 1
    assert fn_chunk.end_line >= fn_chunk.start_line


def test_chunker_javascript_handles_function_class_and_arrow():
    chunks = CodeChunker().chunk_file("src/foo.ts", JS_FILE)
    types = {c.chunk_type for c in chunks}
    assert "module" in types
    assert "function" in types
    assert "class" in types
    names = " ".join(c.chunk_text for c in chunks)
    assert "alpha" in names and "Beta" in names and "gamma" in names


def test_chunker_unsupported_falls_back_to_blocks():
    chunks = CodeChunker().chunk_file("notes.txt", "line\n" * 120)
    assert chunks[0].chunk_type == "module"
    assert any(c.chunk_type == "block" for c in chunks)


def test_chunker_empty_file_returns_no_chunks():
    assert CodeChunker().chunk_file("a.py", "") == []


# ---------------------------------------------------------------------------
# Embedder (mock path is deterministic)
# ---------------------------------------------------------------------------

def test_embedder_mock_is_deterministic_and_normalized():
    emb = VoyageEmbedder()
    a = asyncio.new_event_loop().run_until_complete(emb.embed_query("hello"))
    b = asyncio.new_event_loop().run_until_complete(emb.embed_query("hello"))
    assert a == b
    assert len(a) == emb.dim
    norm_sq = sum(x * x for x in a)
    assert 0.99 <= norm_sq <= 1.01


# ---------------------------------------------------------------------------
# Fusion + recency
# ---------------------------------------------------------------------------

def _chunk(cid: str, score: float = 0.0, last: datetime | None = None) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=cid,
        file_path=f"f/{cid}.py",
        chunk_text=f"text-{cid}",
        start_line=1,
        end_line=10,
        score=score,
        last_commit_at=last,
    )


def test_rrf_merges_two_lists_and_rewards_chunks_in_both():
    bm25 = [_chunk("a"), _chunk("b"), _chunk("c")]
    dense = [_chunk("b"), _chunk("d"), _chunk("a")]
    fused = reciprocal_rank_fusion(bm25, dense, k=60, top_n=4)
    ids = [c.chunk_id for c in fused]
    # chunks present in both lists must outrank chunks present in only one.
    assert ids[0] in {"a", "b"}
    assert set(ids) == {"a", "b", "c", "d"}


def test_recency_boost_promotes_recent_chunks_over_stale_ones():
    now = datetime.utcnow()
    fresh = _chunk("fresh", score=0.10, last=now - timedelta(days=1))
    stale = _chunk("stale", score=0.11, last=now - timedelta(days=400))
    boosted = apply_recency_boost([fresh, stale], now=now, boost_max=0.1, half_life_days=30)
    assert boosted[0].chunk_id == "fresh"
    assert boosted[0].score > 0.11


def test_recency_boost_is_noop_when_no_timestamps():
    chunk = _chunk("none", score=0.5)
    out = apply_recency_boost([chunk])
    assert out[0].score == 0.5


# ---------------------------------------------------------------------------
# Query builder
# ---------------------------------------------------------------------------

def test_query_builder_uses_file_stem_and_hunk_function_names():
    fc = FileChange(
        path="auth/middleware.py",
        status="modified",
        additions=2,
        deletions=1,
        hunks=["@@ -10,3 +10,4 @@ def validateJWT(token):"],
    )
    q = build_query_for_file(fc)
    assert "middleware" in q
    assert "validateJWT" in q


# ---------------------------------------------------------------------------
# Context assembler
# ---------------------------------------------------------------------------

def test_context_assembler_includes_diff_and_chunks_within_budget():
    diff = "diff --git a/x.py\n@@ -1,1 +1,2 @@\n+print('hi')\n"
    chunks = [
        _chunk("c1", score=0.3),
        _chunk("c2", score=0.2),
        _chunk("c3", score=0.1),
    ]
    out = ContextAssembler(token_budget=2000, diff_share=0.5).assemble(diff, chunks)
    assert "## Diff" in out.text
    assert "## Retrieved context" in out.text
    assert out.chunks_included >= 1
    assert out.total_tokens <= 2200  # small slack for tiktoken vs heuristic


def test_context_assembler_truncates_when_chunks_exceed_budget():
    diff = ""
    big = RetrievedChunk(
        chunk_id="big",
        file_path="big.py",
        chunk_text="x" * 100_000,
        start_line=1,
        end_line=2_000,
        score=1.0,
        last_commit_at=None,
    )
    out = ContextAssembler(token_budget=500, diff_share=0.0).assemble(diff, [big])
    assert "[chunk truncated]" in out.text
    assert out.chunks_included == 1
    assert out.chunks_truncated == 1


def test_context_assembler_handles_no_chunks_gracefully():
    out = ContextAssembler(token_budget=1000).assemble("diff text", [])
    assert "## Retrieved context" not in out.text
    assert out.chunks_included == 0
    assert out.chunks_truncated == 0
