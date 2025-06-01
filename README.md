<div align="center">

# Sentinel

**AI-Powered Code Review with Reproducible Evaluation**

[![CI](https://github.com/Vyshnavi-d-p-3/sentinel/actions/workflows/ci.yml/badge.svg)](https://github.com/Vyshnavi-d-p-3/sentinel/actions)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Next.js 14](https://img.shields.io/badge/Next.js-14-black.svg)](https://nextjs.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

*A GitHub App that reviews pull requests using hybrid retrieval + LLM synthesis,*
*backed by a 100-PR hand-labeled evaluation harness with per-category P/R/F1.*

[Architecture](#architecture) · [Quick Start](#quick-start) · [Evaluation](#evaluation-methodology) · [Tech Stack](#tech-stack) · [Roadmap](#roadmap)

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

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                           GITHUB.COM                                 │
│   PR opened ──webhook──►     │     ◄──Check Runs API── Comments      │
└──────────────────────────────┼───────────────────────────────────────┘
                               │ POST /webhook/github
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│                        FASTAPI BACKEND                               │
│                                                                      │
│  ┌────────────┐    ┌──────────────────┐    ┌─────────────────────┐  │
│  │  Webhook    │───►│   Review          │───►│  GitHub Client      │  │
│  │  Router     │    │   Orchestrator    │    │  (Check Runs API)   │  │
│  │  • HMAC     │    │  • parse diff     │    └─────────────────────┘  │
│  │  • route    │    │  • retrieve ctx   │    ┌─────────────────────┐  │
│  └────────────┘    │  • call LLM       │───►│  Cost Guard         │  │
│                     │  • structure out   │    │  • $2/day budget    │  │
│  ┌────────────┐    └────────┬───────────┘    │  • per-PR cap       │  │
│  │ Dashboard  │             │                │  • circuit breaker   │  │
│  │ API        │             ▼                └─────────────────────┘  │
│  │ /reviews   │    ┌──────────────────┐    ┌─────────────────────┐  │
│  │ /eval      │    │ Hybrid Retriever │    │  LLM Gateway        │  │
│  │ /costs     │    │  BM25 (tsvector) │    │  • Claude / GPT-4o  │  │
│  │ /prompts   │    │  Dense (pgvector) │    │  • retry + backoff  │  │
│  └────────────┘    │  RRF merge → top5│    │  • Langfuse tracing │  │
│                     └──────────────────┘    └─────────────────────┘  │
└──────────────────────────────┬───────────────────────────────────────┘
                               │
          ┌────────────────────┼────────────────────┐
          ▼                    ▼                     ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│  PostgreSQL 16   │  │  Eval Harness    │  │  Next.js 14      │
│  + pgvector      │  │  (CI / manual)   │  │  Dashboard       │
│                  │  │                  │  │                  │
│  repos           │  │  100 labeled PRs │  │  /reviews        │
│  reviews         │  │  P/R/F1 per cat  │  │  /eval           │
│  prompts         │  │  regression gate │  │  /costs          │
│  eval_runs       │  │  ΔF1 < 5%       │  │  /prompts        │
│  cost_ledger     │  │                  │  │  /settings       │
│  repo_embeddings │  │                  │  │                  │
└──────────────────┘  └──────────────────┘  └──────────────────┘
```

### Retrieval Pipeline

```
PR Diff
  │
  ▼
┌─────────────────┐
│   Diff Parser    │  Extract changed files, functions, ±10 lines context
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
│ Context Assembly │  Diff + retrieved chunks → truncate to token budget
└─────────────────┘
```

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Backend | FastAPI, Python 3.12+ | API server, webhook handler |
| Validation | Pydantic v2 | Structured LLM output with type safety |
| Database | PostgreSQL 16 + pgvector | Reviews, prompts, evals, code embeddings |
| Text Search | PostgreSQL tsvector | BM25-equivalent full-text retrieval |
| Frontend | Next.js 14 (App Router) | Dashboard SPA |
| UI | Tailwind CSS + shadcn/ui | Component library |
| Charts | Recharts | F1 trend visualizations |
| LLM | Claude Sonnet / GPT-4o | Review generation |
| Observability | Langfuse | Token tracking, trace logging |
| Eval | Custom Python harness | P/R/F1 per category |
| CI/CD | GitHub Actions | Lint, test, eval regression gate |

## Evaluation Methodology

**Dataset:** 100 hand-labeled PRs from 5 OSS repos (Next.js, FastAPI, Flask, LangChain, Express). Each PR has 2–5 expected comments across 4 categories (security, bug, performance, style) at 4 severity levels. Includes `expected_no_comments` entries for false positive detection.

**Scoring:** Per-category precision, recall, F1 with fuzzy matching — file path exact, line number ±5 tolerance, category exact.

**CI Gate:** Any prompt or model change that drops a category F1 by more than 5% from baseline fails the build.

## Quick Start

```bash
git clone https://github.com/Vyshnavi-d-p-3/sentinel.git
cd sentinel

# Infrastructure
docker compose up -d

# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload

# Dashboard (separate terminal)
cd dashboard && npm install && npm run dev
```

## Project Structure

```
sentinel/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI entry point
│   │   ├── config.py               # pydantic-settings config
│   │   ├── routers/                # webhook, reviews, eval, costs, prompts
│   │   ├── services/               # orchestrator, diff_parser, cost_guard, llm_gateway
│   │   ├── retrieval/              # embedder, bm25, dense, fusion (RRF)
│   │   ├── models/                 # ORM, schemas, structured output
│   │   └── core/                   # database session, HMAC security
│   ├── tests/                      # unit, integration, fixtures
│   ├── migrations/                 # Alembic
│   └── Dockerfile
├── dashboard/                      # Next.js 14 App Router
│   └── src/app/                    # reviews, eval, costs, prompts, settings
├── eval/
│   ├── fixtures/                   # 100 labeled PRs (JSON)
│   └── scripts/                    # eval_runner.py, scoring.py
├── docker-compose.yml
└── .github/workflows/              # ci.yml, eval.yml
```

## Roadmap

- [x] Architecture design + database schema
- [x] Project scaffold with core modules
- [x] Diff parser with context extraction
- [x] Cost guard — budget + circuit breaker
- [x] Hybrid retrieval — RRF fusion
- [x] Eval scoring engine (P/R/F1 per category)
- [ ] LLM Gateway with Langfuse tracing
- [ ] GitHub App integration (webhooks → Check Runs)
- [ ] Eval dataset — labeling 100 PRs
- [ ] CI regression gate
- [ ] Next.js dashboard
- [ ] Deploy: Railway + Vercel + Neon
- [ ] Blog post + demo video

## License

MIT — see [LICENSE](LICENSE) for details.

---

<div align="center">
<sub>Built by <a href="https://github.com/Vyshnavi-d-p-3">Vyshnavi D P</a></sub>
</div>
