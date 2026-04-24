# Outside the repository: deploy, content, and real benchmarks

The codebase ships pipelines, a dashboard, and an eval harness. The items below require **operator time**, **cloud accounts**, or **curation**—they are not incomplete features in the source tree; they are **deliverables you produce** using the repo as the engine.

## 1. Production deploy

- **Reference:** [`DEPLOY.md`](DEPLOY.md) (Postgres + pgvector, FastAPI container, Vercel dashboard, GitHub App wiring).
- **Accurate claim:** *“A documented path to production exists; a specific public URL is not part of the git artifact.”* After deploy, cite your own API and dashboard URLs in the blog and video.
- **Pre-flight:** `alembic upgrade head`, `ENVIRONMENT=production`, `DB_AUTO_CREATE_TABLES=false`, `LLM_MOCK_MODE=false` when using paid inference, `API_KEY` + matching `NEXT_PUBLIC_API_KEY` if the UI calls the API from the browser.

## 2. Blog post (draft in-repo)

- **Draft:** [`BLOG_DRAFT.md`](BLOG_DRAFT.md). Before publishing, align every quantitative claim with what you actually ran (CI vs `--no-mock` vs a hand-labeled slice).
- **Credible story:** *CI proves harness stability on mock-aligned data;* *reported F1 on real PRs* requires a separate eval run and dataset description.

## 3. Demo video (outline in-repo)

- **Outline:** [`VIDEO_OUTLINE.md`](VIDEO_OUTLINE.md). Record only flows you can reproduce (local `docker compose`, or your deployed stack). If you show the Eval page, state whether numbers come from **disk/DB artifacts** and whether they reflect **synthetic** or **real-LLM** eval.

## 4. A real hand-labeled benchmark (optional, high effort)

**What the repo does *not* include:** 100 statistically diverse, independently adjudicated PRs from five OSS orgs. That is **research/ops work**, not a missing file.

**How to build one (summary):**

1. **Sampling:** Choose repos, time window, and inclusion rules (e.g. security-relevant file paths) *before* labeling—write them down to avoid selection bias in the write-up.
2. **Rubric:** Follow [`eval/scripts/labeling_rubric.md`](../eval/scripts/labeling_rubric.md) so labels stay comparable across PRs.
3. **Format:** One JSON per PR matching the eval fixture schema (see any `synth_pr_*.json` for required fields, or `eval/fixtures/legacy/` for hand-authored examples).
4. **Execution:** `eval_runner.py` with **real** keys (`--no-mock` when appropriate), fixed model version, and frozen prompt hash. Store `eval/results.json` and/or persist eval runs to the DB for the dashboard.
5. **Reporting:** Report N, label distribution, inter-rater agreement if multiple annotators, and failure modes. Do not conflate that run with the **default CI** bundle.

**Aspirational line you may use in marketing** only *after* you have done the work: *“We evaluated on N hand-labeled pull requests from …”* with N and methodology explicit.

## 5. Checklist before claiming “the proposal is done”

| Claim | In-repo? | You must |
|--------|----------|----------|
| Regression-gated eval in CI | Yes | — |
| 100-PR *CI* dataset | Yes (synthetic) | — |
| Diverse *human* labels at scale | No | Curate + run eval (above) |
| Public URLs | No | Deploy ([`DEPLOY.md`](DEPLOY.md)) |
| Blog / video / App install in production | No | Publish + configure GitHub App on your org |

This document is the single place to point stakeholders when they ask what remains **outside** git.
