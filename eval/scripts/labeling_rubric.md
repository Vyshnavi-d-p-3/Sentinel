# Sentinel Labeling Rubric

This document defines the rules for hand-labeling PR fixtures used by the
Sentinel evaluation harness. Consistent labeling is the difference between
trustworthy F1 numbers and noise.

## Core principle

> Label what a senior engineer would actually flag in a serious code review,
> not what is "nice to have."

If you would not bring it up in a real review, do not label it.

## Mandatory fields per labeled comment

Every entry in `expected_comments` must include:

- `file` — exact file path as it appears in the diff (post-rename path if renamed)
- `line` — exact 1-indexed line number in the **post-image** of the diff
- `category` — one of: `security`, `bug`, `performance`, `style`, `suggestion`
- `severity` — one of: `critical`, `high`, `medium`, `low`
- `description` — one-sentence explanation of why this is an issue

Optional but encouraged:

- `severity` calibrated using the table below
- `description` includes the failure mode, not just the symptom

## Categories (with examples)

| Category      | Label when…                                                                 | Examples                                                              |
| ------------- | --------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| `security`    | The code introduces or fails to mitigate a real attack vector               | SQL injection, XSS, auth bypass, secrets in code, weak crypto         |
| `bug`         | The code is logically incorrect or has a defect that will manifest at runtime | Null deref, off-by-one, race condition, wrong operator, wrong type    |
| `performance` | The code does meaningfully more work than necessary on a hot path           | N+1 queries, missing index, sync I/O in async path, O(n²) on big data |
| `style`       | The code is confusing or inconsistent in a way that creates future bugs      | Misleading variable name, dead branch, shadowed variable              |
| `suggestion`  | A meaningful improvement that is not strictly a defect                       | Use stdlib helper, extract a constant, prefer a context manager       |

> Pure formatting (whitespace, quote style, line length) is **not** a label.
> If your project's formatter would catch it, do not label it.

## Severity calibration

| Severity   | Meaning                                                       |
| ---------- | ------------------------------------------------------------- |
| `critical` | Will likely break production or expose data on first request  |
| `high`     | Likely bug or vuln that must be fixed before merge            |
| `medium`   | Should be fixed before merge but is unlikely to break prod    |
| `low`      | Worth mentioning, would not block merge                       |

## Anti-patterns — do NOT label

- **Missing tests.** Sentinel does not flag missing tests; reviewers do.
- **Style matching project conventions.** If the project uses 4-space indent
  and the diff uses 4-space indent, that is fine even if you prefer 2.
- **Acknowledged TODOs.** A `# TODO(team)` already documented is not a flag.
- **Refactoring opportunities.** "You could split this into two functions" is
  not a finding unless the current shape is actually a defect.
- **Things you cannot point at.** A label without a specific line number is
  not actionable and must not appear in `expected_comments`.

## Per-PR targets

- **Realistic comment count:** 2–5 comments per PR. PRs with 10+ labels are a
  smell — split them or remove low-signal labels.
- **Category balance across the dataset:** roughly 25% security, 30% bug,
  15% performance, 15% style, 15% suggestion. Use `consistency_check.py` to
  monitor drift.
- **~10 intentionally clean PRs** — set `"clean_pr": true` and leave
  `expected_comments` empty. These measure false positive rate when the model
  should stay silent.
- **~5 tricky-but-correct PRs** — set `expected_no_comments` to capture
  patterns the model commonly misfires on (e.g. correct-looking auth code).

## Fixture schema

```jsonc
{
  "pr_id": "fastapi_pr_12345",         // unique identifier
  "repo": "tiangolo/fastapi",          // owner/name
  "pr_number": 12345,
  "pr_title": "Fix SQL injection in query builder",
  "diff": "diff --git a/...",          // unified diff text
  "clean_pr": false,                    // optional, default false
  "expected_comments": [
    {
      "file": "app/db.py",
      "line": 12,
      "category": "security",
      "severity": "critical",
      "description": "User input directly interpolated into SQL string."
    }
  ],
  "expected_no_comments": [],          // patterns the model must NOT flag
  "context_files": {                   // OPTIONAL — used by ablation.py only
    "app/auth/session.py": [
      "SESSION_TTL_SECONDS = 1800  # contract: tokens expire after 30 minutes",
      "def issue_session(user_id: str) -> Session: ..."
    ]
  }
}
```

### `context_files` (optional, ablation only)

Maps a changed file path → ordered list of code snippets that the **retrieval
ablation harness** (`eval/scripts/ablation.py`) injects as if the hybrid
retriever had returned them. Use this to label fixtures where the correct
review depends on context the diff alone does not contain (a contract defined
in another file, a constant the diff is meant to honor, etc.).

The regular `eval_runner.py` ignores this field — only the ablation harness
reads it. Mock-mode runs will show ~0 delta because the mock LLM ignores the
prompt; real-mode runs (`--no-mock`) measure the F1 lift.

## When you change the rubric

Bump the dataset version in the baseline header, re-run the eval, and commit
the new baseline. Otherwise CI will report regressions that are actually
re-labelings.
