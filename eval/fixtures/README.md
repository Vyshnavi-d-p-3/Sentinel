# Eval Fixtures

Pull-request JSON files drive the P/R/F1 harness (`eval/scripts/eval_runner.py`).

## Contents

**98 hand-authored eval fixtures** with realistic-style diffs spanning five OSS ecosystems (FastAPI, Next.js, Flask, LangChain, Express). Each file includes:

- `is_clean` — when true, the PR is used for false-positive rate (no `expected_comments`).
- `expected_comments` — file, line, category, severity, description.
- Optional `expected_no_comments` — lines that should not be flagged (for nuanced clean PRs).

Regenerate files (overwrites `pr_*.json` in this directory):

```bash
python eval/scripts/generate_realistic_fixtures.py
```

## Schema

```json
{
  "pr_id": "fastapi_pr_10842",
  "repo": "tiangolo/fastapi",
  "pr_number": 10842,
  "pr_title": "…",
  "is_clean": false,
  "diff": "diff --git a/…",
  "expected_comments": [
    {
      "file": "app/api/routes/users.py",
      "line": 10,
      "category": "security",
      "severity": "critical",
      "description": "…"
    }
  ],
  "expected_no_comments": []
}
```

## Labeling

See [`../scripts/labeling_rubric.md`](../scripts/labeling_rubric.md).
