# ADR-001: Why a 4-Step Pipeline Instead of Single Prompt

## Status: Accepted
## Date: 2026-04-15

## Context
Initial prototype used a single prompt for review. Testing on 30 PRs showed ~60% line number accuracy on diffs >3000 tokens. The model's attention degraded on files later in the diff.

## Decision
Decompose into 4 steps: triage, deep review (per-file), cross-reference, synthesis. Each step gets a focused prompt and output schema.

## Consequences
- Line accuracy improved to ~94%
- Token usage increased ~30% (4 calls vs 1)
- Triage step saves 30-40% by skipping non-code files, net positive
- Each step can be independently optimized and evaluated

## Alternatives Considered
- 2-step (triage + review): missed cross-file issues
- 6-step (add per-file synthesis + final): diminishing returns, added latency
