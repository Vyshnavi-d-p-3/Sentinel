# Publishing, Deployment, and Benchmark Guide

The codebase ships pipelines, a dashboard, and an eval harness. This document covers what requires **operator time**, **cloud accounts**, or **additional curation**.

## 0. Repository map

- **Eval harness:** [`eval/README.md`](../eval/README.md) (runner, scoring, fixtures, baseline).
- **GitHub App setup:** [`GITHUB_APP_SETUP.md`](GITHUB_APP_SETUP.md) (registration, permissions, webhooks).
- **Deployment:** [`DEPLOY.md`](DEPLOY.md) (Postgres + pgvector, FastAPI container, Vercel dashboard).

## 1. Production deploy

- **Reference:** [`DEPLOY.md`](DEPLOY.md) and `backend/Procfile`, `backend/fly.toml`, `dashboard/vercel.json`.
- **Pre-flight:** `alembic upgrade head`, `ENVIRONMENT=production`, `DB_AUTO_CREATE_TABLES=false`, `LLM_MOCK_MODE=false` with valid API keys, `API_KEY` for dashboard API routes, `GITHUB_WEBHOOK_SECRET` matching the GitHub App.
- **Infrastructure:** Backend on Railway or Fly.io; dashboard on Vercel; database on Neon or Supabase (Postgres + pgvector).

## 2. Eval dataset

| Asset | Status | Notes |
|-------|--------|-------|
| Eval harness (runner + scorer) | In repo | Strict + soft matching, clean-PR FP rate |
| 98 realistic-style fixtures | In repo | [`eval/fixtures/`](../eval/fixtures/README.md), `generate_realistic_fixtures.py` |
| CI regression gate | In repo | Fails if strict per-category F1 drops more than the threshold vs baseline |
| Real-LLM baseline | Operator | Run `eval_runner.py --no-mock` with API keys, then copy `eval/results.json` to `eval/baselines/baseline.json` |

### Establishing a real baseline

```bash
export ANTHROPIC_API_KEY=9383ab45-2b27-49e2-8079-d9533cbc1b7c
cd backend
python ../eval/scripts/eval_runner.py \
  --no-mock \
  --fixtures ../eval/fixtures/ \
  --output ../eval/results.json
cp ../eval/results.json ../eval/baselines/baseline.json
```

## 3. Blog post

- **Draft:** [`BLOG_DRAFT.md`](BLOG_DRAFT.md) — replace placeholder metrics with numbers from a real eval run before publishing.
- **Video outline:** [`VIDEO_OUTLINE.md`](VIDEO_OUTLINE.md)

## 4. Checklist before claiming “done”

| Claim | Action |
|-------|--------|
| Regression-gated eval in CI | In repo — keep baseline updated when intentionally changing prompts |
| 98 fixture dataset | In repo — regenerate with `generate_realistic_fixtures.py` if you change the generator |
| Real-LLM baseline numbers | Run `--no-mock` eval and update `baseline.json` |
| Public deploy | Deploy API + DB + dashboard; follow `DEPLOY.md` |
| GitHub App on real repos | Follow `GITHUB_APP_SETUP.md` |
| Blog / video | Fill metrics, publish externally |

This document is the single place for **outside-git** work: deploy, content, and defensible benchmark claims.
