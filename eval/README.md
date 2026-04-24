# Evaluation harness

Offline tooling that scores review output against **fixture-defined labels** (per-category P/R/F1, soft match, clean-PR false positives). The harness is the same for CI synthetics, legacy examples, and future hand-labeled sets—only the JSON inputs differ.

| Path | Role |
|------|------|
| [`scripts/eval_runner.py`](scripts/eval_runner.py) | Load fixtures, run the orchestrator, write `eval/results.json`, optional `--gate` vs baseline |
| [`scripts/scoring.py`](scripts/scoring.py) | Strict/soft matching, per-category metrics |
| [`scripts/generate_synthetic_fixtures.py`](scripts/generate_synthetic_fixtures.py) | Regenerate the 100 mock-aligned `synth_pr_*.json` files |
| [`scripts/labeling_rubric.md`](scripts/labeling_rubric.md) | Conventions for human-authored ground truth |
| [`fixtures/`](fixtures/) | CI glob: `synth_pr_*.json`; [`fixtures/legacy/`](fixtures/legacy/) for hand-curated examples (not in default CI glob) |
| [`baselines/baseline.json`](baselines/baseline.json) | Strict F1 reference for the regression gate (`eval.yml`) |

**Claims:** default CI uses **synthetic** labels aligned to the mock LLM. For methodology when publishing results or extending labels, read [`../docs/PUBLISHING_AND_BENCHMARK.md`](../docs/PUBLISHING_AND_BENCHMARK.md).
