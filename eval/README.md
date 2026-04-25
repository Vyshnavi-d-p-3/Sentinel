# Evaluation Harness

Offline tooling that scores review output against **hand-labeled fixtures** using per-category P/R/F1, strict and soft matching, and clean-PR false-positive rate.

| Path | Role |
|------|------|
| [`scripts/eval_runner.py`](scripts/eval_runner.py) | Load fixtures, run the orchestrator, score, optional `--gate` vs baseline |
| [`scripts/scoring.py`](scripts/scoring.py) | Strict/soft matching, per-category metrics, clean-PR FP rate |
| [`scripts/generate_realistic_fixtures.py`](scripts/generate_realistic_fixtures.py) | Regenerate the 98 realistic `pr_*.json` fixtures |
| [`scripts/labeling_rubric.md`](scripts/labeling_rubric.md) | Conventions for ground truth |
| [`scripts/ablation.py`](scripts/ablation.py) | Ablation studies |
| [`scripts/consistency_check.py`](scripts/consistency_check.py) | Schema validation for fixtures |
| [`fixtures/`](fixtures/) | 98 JSON fixtures + [`fixtures/README.md`](fixtures/README.md) |
| [`baselines/baseline.json`](baselines/baseline.json) | Strict F1 reference for the CI regression gate |

## Quick start

```bash
# Mock mode (no API keys)
python eval/scripts/eval_runner.py --fixtures eval/fixtures/ --output eval/results.json

# Real LLM (requires provider keys)
python eval/scripts/eval_runner.py --no-mock --output eval/results.json

# CI gate: fail if any category strict F1 drops more than 5% vs baseline
python eval/scripts/eval_runner.py --gate --threshold 0.05 --fixtures eval/fixtures/ --baseline eval/baselines/baseline.json
```

## Methodology

See [`../docs/PUBLISHING_AND_BENCHMARK.md`](../docs/PUBLISHING_AND_BENCHMARK.md).
