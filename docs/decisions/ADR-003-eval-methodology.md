# ADR-003: Evaluation Methodology for Code Review Quality

## Status: Accepted
## Date: 2026-04-17

## Context
The project needed a repeatable evaluation approach that could detect regressions and support prompt/model iteration. Early experiments with LLM-as-judge produced unstable scores and frequent agreement drift across runs, making trend analysis unreliable.

## Decision
Adopt a human-labeled fixture methodology with deterministic scoring:
- Use hand-labeled fixtures instead of LLM-as-judge for ground truth
- Score line matches with a +/-5 line tolerance
- Report per-category F1 (security, bug, performance, style, suggestion) as the primary metric, with aggregate metrics as secondary

## Consequences
- Evaluation is reproducible and interpretable across runs
- Labeling requires sustained manual effort and rubric discipline
- Per-category metrics expose targeted regressions that aggregate scores can hide

## Rationale
- Hand-labeled fixtures over LLM-as-judge: better consistency, clearer audit trail, less evaluator drift
- +/-5 line tolerance: accommodates valid nearby-line anchoring while penalizing broad mislocalization
- Per-category F1 over aggregate-only metrics: avoids a dominant class masking regressions in critical categories

## Alternatives Considered
- LLM-as-judge: faster to scale, but unstable and hard to trust for regression gates
- Exact-line-only matching: too strict for realistic comment anchoring behavior
- Aggregate-only F1: simpler dashboarding, but loses category-level diagnostic value
