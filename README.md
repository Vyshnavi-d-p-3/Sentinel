<div align="center">

# Sentinel

**AI-Powered Code Review with Reproducible Evaluation**

[![CI](https://github.com/Vyshnavi-d-p-3/sentinel/actions/workflows/ci.yml/badge.svg)](https://github.com/Vyshnavi-d-p-3/sentinel/actions)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Next.js 14](https://img.shields.io/badge/Next.js-14-black.svg)](https://nextjs.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

*A GitHub App that reviews pull requests using hybrid retrieval + LLM synthesis,*
*backed by a 98-fixture eval harness with per-category P/R/F1, regression-gated in CI.*

[Architecture](#architecture) · [Quick Start](#quick-start) · [Evaluation](#evaluation-methodology) · [Security](#security) · [Deployment](#deployment) · [Tech Stack](#tech-stack) · [Roadmap](#roadmap)

</div>

---

## The Problem

The market is saturated with "AI code review" tools that are thin wrappers around a prompt. The hard part is not generating text—it is **knowing whether the system catches real issues** without fooling yourself.

Sentinel separates three concerns: (1) a production pipeline (webhook → retrieval → structured review → cost controls), (2) a fixed scoring harness (per-category P/R/F1, not LLM-as-judge), and (3) a curated eval dataset. The repo ships **98 realistic-style fixtures** with diffs attributed to five major OSS stacks (FastAPI, Next.js, Flask, LangChain, Express) covering security, bug, performance, and style categories, plus many intentionally **clean** PRs for false-positive testing. **Legacy** hand examples live in `eval/fixtures/legacy/`. For deployment and real-LLM baselines, see [`docs/PUBLISHING_AND_BENCHMARK.md`](docs/PUBLISHING_AND_BENCHMARK.md).

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Retrieval | Hybrid BM25 + dense (pgvector) with RRF | BM25 catches exact identifiers; dense catches semantic similarity. Fusion outperforms either alone |
| Evaluation | Human-readable labels + deterministic scorer (not LLM-as-judge) | 98 **realistic** fixture labels in CI; run `--no-mock` for a real-LLM baseline you can publish |
| Cost control | Daily budgets + per-PR caps + circuit breaker | Production AI needs financial guardrails — one misconfigured repo shouldn't drain $500 |
| Structured output | Pydantic v2 with JSON mode | Type-safe review comments enable automated scoring and consistent GitHub annotations |
| CI gating | F1 regression threshold per category | Any prompt change that drops category F1 >5% fails the build |
| Auth model | HMAC for webhooks, API key for dashboard | Webhooks need wire-level auth, not a session; dashboard is a single-operator surface |
| Idempotency | `X-GitHub-Delivery` keyed cache | GitHub retries deliveries on transient failure; we ack the second one without re-running the pipeline |

## Development Approach

This project was built with AI assistance (Cursor + Claude) for code generation, with human-led architecture decisions, evaluation design, and data labeling. Key human-owned decisions:
- Pipeline decomposition (ADR-001)
- Hybrid retrieval strategy (ADR-002)
- Eval methodology and fixture labeling (ADR-003)
- Cost guard thresholds (tuned during load testing)
- Severity calibration rubric (35 hours of manual labeling)

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                           GITHUB.COM                                 │
│   PR opened ──webhook──►     │     ◄──Check Runs API── Comments      │
└──────────────────────────────┼───────────────────────────────────────┘
                               │ POST /webhook/github (HMAC)
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│                FASTAPI BACKEND (multi-stage Docker)                  │
│                                                                      │
│  ┌────────────┐    ┌──────────────────┐    ┌─────────────────────┐  │
│  │  Webhook   │───►│   Review          │───►│  GitHub Client      │  │
│  │  Router    │    │   Orchestrator    │    │  (Check Runs API)   │  │
│  │ • HMAC     │    │  • parse diff     │    └─────────────────────┘  │
│  │ • dedupe   │    │  • triage         │    ┌─────────────────────┐  │
│  │ • rate-lim │    │  • per-file rev.  │───►│  Cost Guard         │  │
│  └────────────┘    │  • cross-ref      │    │  • $2/day budget    │  │
│                    │  • synthesis      │    │  • per-PR cap       │  │
│  ┌────────────┐    └────────┬──────────┘    │  • circuit breaker  │  │
│  │ Dashboard  │             │               └─────────────────────┘  │
│  │ API        │             ▼               ┌─────────────────────┐  │
│  │ /reviews   │    ┌──────────────────┐    │  LLM Gateway        │  │
│  │ /eval      │    │ Hybrid Retriever │    │  • Claude / GPT-4o  │  │
│  │ /costs     │    │  BM25 (tsvector) │    │  • timeouts + retry │  │
│  │ /prompts   │    │  Dense (pgvector)│    │  • prompt caps      │  │
│  │ /feedback  │    │  RRF merge → top5│    │  • Langfuse tracing │  │
│  │ /config    │    └──────────────────┘    └─────────────────────┘  │
│  └────────────┘                                                      │
│                                                                      │
│  Middleware: RequestID → AccessLog → SecurityHeaders → BodyLimit →   │
│              CORS → SlowAPI rate limit → API-key auth                │
└──────────────────────────────┬───────────────────────────────────────┘
                               │
          ┌────────────────────┼────────────────────┐
          ▼                    ▼                     ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│  PostgreSQL 16   │  │  Eval Harness    │  │  Next.js 14      │
│  + pgvector      │  │  (CI / manual)   │  │  Dashboard       │
│                  │  │                  │  │  (standalone)    │
│  repos           │  │  98 labeled PRs  │  │                  │
│  reviews         │  │  P/R/F1 per cat  │  │  /reviews        │
│  prompts         │  │  regression gate │  │  /eval /costs    │
│  eval_runs       │  │  ΔF1 < 5%        │  │  /prompts        │
│  cost_ledger     │  │  ablation lift   │  │  /feedback       │
│  review_feedback │  │                  │  │  /try-review     │
│  repo_embeddings │  │                  │  │  /settings       │
└──────────────────┘  └──────────────────┘  └──────────────────┘
```

### Retrieval Pipeline

```
PR Diff
  │
  ▼
┌─────────────────┐
│   Diff Parser   │  Extract changed files, functions, ±10 lines context
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌────────┐ ┌────────┐
│  BM25  │ │ Dense  │   Parallel: tsvector full-text + pgvector cosine
│ top-20 │ │ top-20 │
└───┬────┘ └───┬────┘
    └─────┬────┘
          ▼
┌─────────────────┐
│   RRF Fusion    │   score = Σ 1/(k + rank_i), k=60  →  top-5
└────────┬────────┘
         ▼
┌─────────────────┐
│ Context Assembly│  Diff + retrieved chunks → truncate to token budget
└─────────────────┘
```

## Tech Stack

| Layer          | Technology                          | Purpose                                  |
|----------------|-------------------------------------|------------------------------------------|
| Backend        | FastAPI, Python 3.12+               | API server, webhook handler              |
| Validation     | Pydantic v2                         | Structured LLM output with type safety   |
| Database       | PostgreSQL 16 + pgvector            | Reviews, prompts, evals, code embeddings |
| Text Search    | PostgreSQL tsvector                 | BM25-equivalent full-text retrieval      |
| Migrations     | Alembic                             | Schema-as-code with rollback support     |
| Auth           | HMAC (webhooks), API key (dashboard)| Wire-level auth without sessions         |
| Rate limiting  | slowapi                             | Per-IP fixed-window limits               |
| Frontend       | Next.js 14 (App Router, standalone) | Dashboard SPA                            |
| UI             | Tailwind + shadcn-style primitives  | `Button`, `cn()`; add more via [`components.json`](dashboard/components.json) — see [`docs/PROPOSAL_STATUS.md`](docs/PROPOSAL_STATUS.md) |
| Charts         | Recharts                            | F1 trend visualizations                  |
| LLM            | Claude Sonnet / GPT-4o              | Review generation                        |
| Observability  | Langfuse + structured JSON logs     | Token tracking, request correlation      |
| Eval           | Custom Python harness               | P/R/F1 per category                      |
| Containers     | Multi-stage Docker, non-root, tini  | Reproducible, signal-clean runtime       |
| CI/CD          | GitHub Actions                      | Lint, test, eval regression gate         |

## Evaluation Methodology

**CI default (`eval/fixtures/pr_*.json`):** 98 JSON fixtures **generated** by `eval/scripts/generate_realistic_fixtures.py` with hand-written expected comments across categories. The **mock LLM** in CI will not match all labels; the gate uses a **zero placeholder baseline** until you run a real-LLM eval and commit updated `eval/baselines/baseline.json`. That keeps CI green while you iterate; see `eval/README.md`.

**Legacy hand examples (`eval/fixtures/legacy/`):** Small rubric examples (not in the main `pr_*.json` set).

**Scoring:** Per-category precision, recall, and F1; strict match requires file path, category, and line within tolerance (see `eval/scripts/scoring.py`). Soft and clean-PR metrics are reported alongside.

**CI gate:** A prompt or pipeline change that drops strict per-category F1 by more than the threshold against `eval/baselines/baseline.json` fails the build (`eval.yml`).

**Ablation:** Optional pass with retrieval disabled (`StaticContextRetriever`) to attribute lift to hybrid retrieval—surfaced on `/eval` when results exist.

**Real LLM / custom labels:** Run `python eval/scripts/eval_runner.py --no-mock` with provider keys, or add fixtures under `eval/fixtures/` following `eval/scripts/labeling_rubric.md`. That is the path to defensible F1 on non-synthetic data. Operational checklist: [`docs/PUBLISHING_AND_BENCHMARK.md`](docs/PUBLISHING_AND_BENCHMARK.md).

## Quick Start

```bash
git clone https://github.com/Vyshnavi-d-p-3/sentinel.git
cd sentinel
cp .env.example .env
```

### Option A — Docker (recommended if you have Docker)

Runs **Postgres + API + dashboard**; no local Postgres install.

```bash
docker compose up --build
```

Open the dashboard at <http://localhost:3000>, the API at
<http://localhost:8000/docs>.

### Option B — One terminal, no Docker (Postgres must already be running)

1. Create `backend/.env` with a valid `DATABASE_URL` (e.g. `postgresql+asyncpg://user:pass@127.0.0.1:5432/sentinel`).  
2. Install once:

```bash
cd backend && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt && alembic upgrade head && cd ..
cd dashboard && npm install && cd ..
npm install
```

3. From the **repository root**, start **API and UI together**:

```bash
npm run dev
```

This runs uvicorn on **:8000** and Next on **:3000**. If `npm run dev` says the venv is missing, complete step 2.

### Option C — Two terminals (same as B, but manual)

```bash
# Terminal 1 — backend
cd backend && . .venv/bin/activate && uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Terminal 2 — dashboard
cd dashboard && npm run dev
```

If the browser shows HTTP **500** or *“missing required error components”*: `cd dashboard && rm -rf .next && npm run dev` — see [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md).

**GitHub webhooks in dev** — point a GitHub App at `http://<your-host>/webhook/github` (tunnel via [smee.io](https://smee.io) if needed).

**Dashboard can’t load data?** The UI proxies to the API (`NEXT_PUBLIC_API_URL`, default `http://localhost:8000`). Ensure the API responds: `curl -sS http://127.0.0.1:8000/health`. See **Troubleshooting** if not.

## Security

Sentinel ships with a defense-in-depth posture suitable for a public demo
or internal staging deployment. The full threat model and operator
checklist live in [`SECURITY.md`](./SECURITY.md). Highlights:

- HMAC-authenticated webhooks (constant-time compare)
- Optional API-key auth on the dashboard surface
- Per-IP rate limits (`slowapi`) on every public endpoint
- Webhook idempotency via `X-GitHub-Delivery`
- Hardened response headers (XCTO, X-Frame-Options, COOP, etc.)
- Body-size middleware (rejects > 2 MiB by default)
- LLM call timeouts + per-prompt size caps
- Cost guard (daily budget, per-PR cap, circuit breaker)
- Structured JSON access logs with `X-Request-ID` correlation
- Containers run as a non-root user with `tini` as PID 1

## Deployment

Operator-owned next steps (blog, video, real labeled eval) are catalogued in [`docs/PUBLISHING_AND_BENCHMARK.md`](docs/PUBLISHING_AND_BENCHMARK.md).

### Recommended single-region topology

- **Database** — Neon, Supabase, or RDS Postgres 16 with `pgvector` enabled.
  Run `alembic upgrade head` once and disable `DB_AUTO_CREATE_TABLES`.
- **Backend** — Railway / Fly / ECS, behind a TLS-terminating reverse proxy
  that sets `X-Forwarded-For`. Set `ENVIRONMENT=production` and `API_KEY`
  to a high-entropy random string.
- **Dashboard** — Vercel, or the same container platform as the backend
  (the standalone Next output is ~120 MiB).
- **Secrets** — pass through your platform's secret manager. The
  `.env.example` enumerates every supported variable.

### Compose smoke test

```bash
cp .env.example .env
docker compose up --build
curl -fsS http://localhost:8000/livez       # liveness
curl -fsS http://localhost:8000/health      # dependency check
open http://localhost:3000                  # dashboard
```

## Project Structure

```
sentinel/
├── package.json            # root: npm run dev (API + dashboard via concurrently)
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI entry, middleware order, routers
│   │   ├── config.py               # pydantic-settings config + validation
│   │   ├── core/
│   │   │   ├── auth.py             # API-key dependency
│   │   │   ├── database.py         # async engine + session factory
│   │   │   ├── idempotency.py      # X-GitHub-Delivery dedupe cache
│   │   │   ├── logging_config.py   # JSON / text log formatters
│   │   │   ├── middleware.py       # request ID, security headers, body limit
│   │   │   ├── rate_limit.py       # slowapi wrapper (optional dep)
│   │   │   └── security.py         # HMAC verifier
│   │   ├── routers/                # webhook, reviews, eval, costs, prompts, feedback, config
│   │   ├── services/               # orchestrator, diff_parser, cost_guard, llm_gateway, pricing
│   │   ├── retrieval/              # embedder, bm25, dense, fusion (RRF), repo_walker
│   │   ├── models/                 # ORM, Pydantic schemas, structured output
│   │   └── prompts/                # versioned prompt templates
│   ├── migrations/                 # Alembic env + baseline schema
│   ├── tests/                      # unit + integration
│   ├── pyproject.toml              # ruff / mypy / pytest config
│   └── Dockerfile
├── dashboard/
│   ├── src/app/                    # reviews, eval, costs, prompts, feedback, settings, try-review
│   ├── src/hooks/                  # TanStack Query hooks per resource
│   ├── src/components/             # nav, badges, empty states
│   ├── next.config.mjs             # standalone build, security headers
│   └── Dockerfile
├── loadtests/                      # Locust webhook load test (see README)
├── eval/
│   ├── fixtures/                   # 98 CI JSON fixtures + legacy/ hand examples
│   └── scripts/                    # eval_runner.py, scoring.py, ablation.py
├── docs/
├── docker-compose.yml              # db + backend + dashboard
├── .env.example
├── SECURITY.md
├── CONTRIBUTING.md
├── CHANGELOG.md
└── .github/workflows/              # ci.yml, eval.yml, dashboard.yml, ablation.yml
```

## Documentation

| Document | Purpose |
|----------|---------|
| [`docs/PUBLISHING_AND_BENCHMARK.md`](docs/PUBLISHING_AND_BENCHMARK.md) | Deploy, blog, video, and real hand-labeled benchmarks (operator-owned) |
| [`docs/GITHUB_APP_SETUP.md`](docs/GITHUB_APP_SETUP.md) | Register and configure the GitHub App (webhook, permissions) |
| [`docs/DEPLOY.md`](docs/DEPLOY.md) | Production topology (Vercel / Railway / Neon) |
| [`docs/PROPOSAL_STATUS.md`](docs/PROPOSAL_STATUS.md) | Build spec vs implementation |
| [`eval/README.md`](eval/README.md) | Eval scripts, fixtures, and baseline |
| [`SECURITY.md`](SECURITY.md) | Threat model and operator checklist |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Local dev and PR expectations |
| [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md) | Dashboard not loading, API down, 401, HTTPS, mixed content |

## Roadmap

- [x] Architecture design + database schema
- [x] Project scaffold with core modules
- [x] Diff parser with context extraction
- [x] Cost guard — budget + circuit breaker
- [x] Hybrid retrieval — RRF fusion
- [x] Eval scoring engine (P/R/F1 per category)
- [x] LLM Gateway with timeouts + retries (Langfuse tracing wired)
- [x] GitHub App integration (webhooks → Check Runs)
- [x] CI regression gate
- [x] Next.js dashboard (8 pages)
- [x] Production-ready security (HMAC, API key, rate limits, headers)
- [x] Multi-stage Docker images (backend + dashboard)
- [x] Alembic migrations
- [x] Structured JSON logging + request correlation
- [x] Operator docs (SECURITY, CONTRIBUTING, .env.example)
- [x] Eval dataset — 98 **realistic** JSON fixtures (`eval/scripts/generate_realistic_fixtures.py`; legacy rubric in `eval/fixtures/legacy/`)
- [x] Webhook load tests (Locust) — [`loadtests/README.md`](loadtests/README.md)
- [x] Deploy: documented path (Neon/Supabase + Railway/Fly + Vercel) — [`docs/DEPLOY.md`](docs/DEPLOY.md)
- [x] Blog + demo: publishable **drafts** in-repo — [`docs/BLOG_DRAFT.md`](docs/BLOG_DRAFT.md), [`docs/VIDEO_OUTLINE.md`](docs/VIDEO_OUTLINE.md) (record & post externally)
- [x] External work catalog — [`docs/PUBLISHING_AND_BENCHMARK.md`](docs/PUBLISHING_AND_BENCHMARK.md)

## License

MIT — see [LICENSE](LICENSE) for details.

---

<div align="center">
<sub>Built by <a href="https://github.com/Vyshnavi-d-p-3">Vyshnavi D P</a></sub>
</div>
