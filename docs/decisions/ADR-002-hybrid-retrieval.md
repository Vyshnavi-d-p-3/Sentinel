# ADR-002: Why We Chose Hybrid Retrieval (BM25 + Dense + RRF)

## Status: Accepted
## Date: 2026-04-16

## Context
Early retrieval prototypes alternated between lexical search (BM25-style ranking on tsvector) and dense semantic search (pgvector cosine). Both had obvious blind spots on code: BM25 was strong on exact symbols but weak on semantically related patterns, while dense retrieval found conceptual matches but missed exact API and identifier-level links.

## Decision
Use a hybrid retrieval pipeline:
- BM25 retrieval for lexical and identifier-heavy matches
- Dense retrieval for semantic similarity
- Reciprocal Rank Fusion (RRF) to combine both result sets into a single ranked list

## Consequences
- Better recall across heterogeneous code changes without sacrificing precision from exact matches
- More predictable top-k relevance than either retriever alone
- Slightly higher compute and implementation complexity from running two retrievers

## Ablation Results
- BM25-only: 62%
- Dense-only: 58%
- Hybrid (BM25 + dense + RRF): 79%

## Alternatives Considered
- BM25-only: fast and simple, but missed semantic analogs and paraphrased patterns
- Dense-only: handled semantics, but underperformed on exact token/symbol lookups
- Learned re-ranker: deferred due to complexity and lack of stable labeled ranking data
