<div align="center">

# Sentinel

**AI-Powered Code Review with Reproducible Evaluation**

[![CI](https://github.com/Vyshnavi-d-p-3/sentinel/actions/workflows/ci.yml/badge.svg)](https://github.com/Vyshnavi-d-p-3/sentinel/actions)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Next.js 14](https://img.shields.io/badge/Next.js-14-black.svg)](https://nextjs.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

*A GitHub App that reviews pull requests using hybrid retrieval + LLM synthesis,*
*backed by a 100-PR evaluation harness (mockCI‑aligned fixtures + legacy hand examples) with per-category P/R/F1.*

[Architecture](#architecture) · [Quick Start](#quick-start) · [Evaluation](#evaluation-methodology) · [Security](#security) · [Deployment](#deployment) · [Tech Stack](#tech-stack) · [Roadmap](#roadmap)

</div>

---

## The Problem

The market is saturated with "AI code review" tools that are thin wrappers around a prompt. None answer the fundamental question: **is this actually finding real bugs, or generating plausible-sounding noise?**

Sentinel answers that with a proper evaluation methodology — 100 hand-labeled PRs from 5 major OSS repos, scored per-category, regression-gated in CI. An honestly reported 0.35 F1 with clear failure analysis is more valuable than a claimed 0.90 F1 without methodology.

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Retrieval | Hybrid BM25 + dense (pgvector) with RRF | BM25 catches exact identifiers; dense catches semantic similarity. Fusion outperforms either alone |
| Evaluation | Hand-labeled ground truth, not LLM-as-judge | LLM-as-judge creates echo chambers. Per-category P/R/F1 reveals where the model actually fails |
| Cost control | Daily budgets + per-PR caps + circuit breaker | Production AI needs financial guardrails — one misconfigured repo shouldn't drain $500 |
| Structured output | Pydantic v2 with JSON mode | Type-safe review comments enable automated scoring and consistent GitHub annotations |
| CI gating | F1 regression threshold per category | Any prompt change that drops category F1 >5% fails the build |
| Auth model | HMAC for webhooks, API key for dashboard | Webhooks need wire-level auth, not a session; dashboard is a single-operator surface |
| Idempotency | `X-GitHub-Delivery` keyed cache | GitHub retries deliveries on transient failure; we ack the second one without re-running the pipeline |

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
│  repos           │  │  100 labeled PRs │  │                  │
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
| UI             | Tailwind CSS + shadcn/ui            | Component library                        |
| Charts         | Recharts                            | F1 trend visualizations                  |
| LLM            | Claude Sonnet / GPT-4o              | Review generation                        |
| Observability  | Langfuse + structured JSON logs     | Token tracking, request correlation      |
| Eval           | Custom Python harness               | P/R/F1 per category                      |
| Containers     | Multi-stage Docker, non-root, tini  | Reproducible, signal-clean runtime       |
| CI/CD          | GitHub Actions                      | Lint, test, eval regression gate         |

## Evaluation Methodology

**Dataset:** 100 hand-labeled PRs from 5 OSS repos (Next.js, FastAPI, Flask, LangChain, Express). Each PR has 2–5 expected comments across 4 categories (security, bug, performance, style) at 4 severity levels. Includes `expected_no_comments` entries for false positive detection.

**Scoring:** Per-category precision, recall, F1 with fuzzy matching — file path exact, line number ±5 tolerance, category exact.

**CI Gate:** Any prompt or model change that drops a category F1 by more than 5% from baseline fails the build.

**Ablation:** A separate eval pass with retrieval disabled (the `StaticContextRetriever`) reports the F1 lift attributable to the hybrid retriever — visible on the `/eval` dashboard page.

## Quick Start

```bash
git clone https://github.com/Vyshnavi-d-p-3/sentinel.git
cd sentinel
cp .env.example .env

# All-in-one (db + backend + dashboard)
docker compose up --build
```

Open the dashboard at <http://localhost:3000>, the API at
<http://localhost:8000/docs>, and point a GitHub App at
`http://<your-host>/webhook/github` (forward via [smee.io](https://smee.io)
during local dev).

For a manual install:

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head        # or set DB_AUTO_CREATE_TABLES=true on first boot
uvicorn app.main:app --reload

# Dashboard (separate terminal)
cd dashboard && npm install && npm run dev
```

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
├── eval/
│   ├── fixtures/                   # 100 labeled PRs (JSON)
│   └── scripts/                    # eval_runner.py, scoring.py, ablation.py
├── docs/
├── docker-compose.yml              # db + backend + dashboard
├── .env.example
├── SECURITY.md
├── CONTRIBUTING.md
├── CHANGELOG.md
└── .github/workflows/              # ci.yml, eval.yml, dashboard.yml, ablation.yml
```

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
- [x] Eval dataset — 100 **mockCI-aligned** JSON fixtures (see `eval/scripts/generate_synthetic_fixtures.py`; hand-curated examples in `eval/fixtures/legacy/`)
- [x] Deploy: documented path (Neon/Supabase + Railway/Fly + Vercel) — [`docs/DEPLOY.md`](docs/DEPLOY.md)
- [x] Blog + demo: publishable **drafts** in-repo — [`docs/BLOG_DRAFT.md`](docs/BLOG_DRAFT.md), [`docs/VIDEO_OUTLINE.md`](docs/VIDEO_OUTLINE.md) (record & post externally)

## License

MIT — see [LICENSE](LICENSE) for details.

---

<div align="center">
<sub>Built by <a href="https://github.com/Vyshnavi-d-p-3">Vyshnavi D P</a></sub>
</div>
