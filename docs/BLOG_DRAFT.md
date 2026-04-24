# I built an AI code reviewer. Here’s how I measured whether it actually works.

*Draft for Medium / dev.to — edit voice, add screenshots, then publish.*

## Hook

The market is full of LLM demos that *sound* like code review. I wanted something defensible: **hand-labeled ground truth**, **precision/recall/F1 per category**, and a **CI gate** that fails when a prompt change breaks security or bug detection.

## What I built (Sentinel)

- GitHub App → **FastAPI** pipeline: diff parse → hybrid **BM25 + dense (pgvector) + RRF** → structured **Pydantic** output → **Check Runs** + cost tracking.
- **100 PR fixtures** and an **eval runner** in CI: compare model comments to labels with line tolerance, **not** LLM-as-judge.
- **Next.js** dashboard: reviews, eval trends, costs, prompts, feedback.

## The uncomfortable truth

A low, honestly reported F1 with a clear failure analysis is more credible than a claimed 0.9 without methodology. I document **where** the model fails (e.g. multi-file bugs, context limits).

## What I’d do next

- More diverse labels (security stress cases).
- Live keys + shadow traffic before trusting production metrics.
- Tighter calibration between model confidence and actual correctness.

## CTA

Link the public repo, a **Loom** walkthrough, and one chart from the **Eval** page.

---

*End of draft.*
