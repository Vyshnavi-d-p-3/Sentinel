# Eval fixtures

Hand-labeled pull requests drive the P/R/F1 harness (`eval/scripts/eval_runner.py`).

## Target size

The project spec calls for **100 JSON fixtures** (minimum useful scale ~50). Add files under this directory; each must include a non-empty `diff` and optional `expected_comments` / `expected_no_comments` per `eval/scripts/labeling_rubric.md`.

## Current progress

Count files: `ls *.json | wc -l` in this directory.

## Adding a fixture

1. Copy `example_pr_001.json` as a template.  
2. Use real unified diff text; avoid synthetic empty hunks.  
3. Re-run:  
   `python eval/scripts/eval_runner.py --fixtures eval/fixtures/ --output eval/results.json`  
4. Update `dataset_version` in `eval_runs` / baseline when the set materially changes.
