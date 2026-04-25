# I Built an AI Code Reviewer — Here’s How I Measured Whether It Works

*Draft for Medium / dev.to. Replace the metrics block with results from your own `eval_runner.py --no-mock` runs.*

## The problem with AI code review

Many tools are thin wrappers: diff in, text out, ship. The harder question is **whether the system finds the right issues** on real code, without grading yourself with another LLM.

## What Sentinel is

A **GitHub App**: webhook → triage and retrieval (BM25 + dense embeddings) → structured review comments (Pydantic) → optional GitHub check runs. The dashboard shows reviews, eval history, and costs.

**Hybrid retrieval** — keyword search for identifiers, dense vectors for similar patterns, fused with RRF.

**Structured output** — every comment has file, line, category, severity, and confidence so scores are reproducible.

**Cost guardrails** — daily budgets, per-PR token caps, circuit breaker on repeated failures.

## The eval harness

The repo ships **98 JSON fixtures** with unified diffs and hand-written labels (security, bug, performance, style, suggestion), plus many **clean** PRs for false-positive testing. The scorer uses **strict** match (file + category + line within tolerance) and **soft** match (file + category). CI can **fail** if strict per-category F1 regresses against `eval/baselines/baseline.json`.

The uncomfortable takeaway: a **low F1 with a clear methodology** beats a high number nobody can reproduce. Run with real API keys, save `eval/results.json`, and cite model + prompt version.

## What I’d do differently

- **Labeling** is the bottleneck, not the model — a serious benchmark needs hundreds of PRs and clear inclusion rules.
- **Token and dollar accounting** should be explicit in the post (input/output prices, not vibes).
- **Feedback** from GitHub (dismiss/resolve) is the start of a real learning loop, not the end.

## Try it

Repo: [github.com/Vyshnavi-d-p-3/sentinel](https://github.com/Vyshnavi-d-p-3/sentinel). See [`PUBLISHING_AND_BENCHMARK.md`](PUBLISHING_AND_BENCHMARK.md) for deploy and benchmark checklist.

---
*End of draft.*
