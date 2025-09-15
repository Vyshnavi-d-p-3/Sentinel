# Build document vs implementation (status)

Tracking the *Sentinel — Complete Build Document* (PDF) against this repository. Use this table in interviews: say what shipped, what is partial, and what lives outside git.

## Tech stack (PDF page 1)

| Layer | PDF | Repo |
|------|-----|------|
| Frontend | Next.js 14 App Router | **Yes** — `dashboard/` |
| UI | Tailwind + **shadcn/ui** | **Partial** — Tailwind + **shadcn-pattern** `Button` (`dashboard/src/components/ui/button.tsx`), `cn()` (`dashboard/src/lib/utils.ts`), `components.json`. Add more primitives with `npx shadcn@latest add …` as needed. |
| Data | TanStack Query v5 | **Yes** — `dashboard/src/hooks/` |
| Charts | Recharts 2.x | **Yes** — e.g. `dashboard/src/app/eval/page.tsx`, costs |
| Backend | FastAPI 0.110+, Pydantic v2 | **Yes** — `backend/app/` |
| DB | Postgres 16 + pgvector + tsvector | **Yes** — SQLAlchemy models + migrations |
| LLM | Claude / GPT-4o + fallback | **Yes** — `backend/app/services/llm_gateway.py` |
| Observability | Langfuse | **Yes** — generations logged when keys set; `langfuse_host` optional |
| Eval | Custom harness, P/R/F1, CI gate | **Yes** — `eval/scripts/`, `.github/workflows/eval.yml` |
| CI | GitHub Actions lint/test/eval | **Yes** — `ci.yml`, `eval.yml`, `dashboard.yml`, optional `loadtest.yml` |
| Deploy | Railway/Fly + Vercel + Neon | **Doc** — [`DEPLOY.md`](DEPLOY.md) |

## Architecture (PDF page 2)

| Block | Status |
|-------|--------|
| Webhook → orchestrator → GitHub client | **Yes** |
| Hybrid retriever (BM25 + dense + RRF) | **Yes** — `backend/app/retrieval/` |
| Cost guard | **Yes** |
| LLM gateway (retry, timeout, JSON, Langfuse) | **Yes** |
| Dashboard API + Next routes | **Yes** |

## PDF phases / deliverables (condensed)

| Area | Spec hint | Status |
|------|------------|--------|
| 100-PR dataset | Hand-labeled JSON fixtures | **100 × synthetic** `eval/fixtures/synth_pr_*.json` (mock-aligned CI); **legacy** hand examples under `eval/fixtures/legacy/` |
| Eval gate | F1 drop vs baseline in CI | **Yes** |
| `GET /eval/compare` | Prompt comparison | **Yes** — backend + dashboard hooks |
| Playwright | Core E2E | **Expanded** — `dashboard/e2e/routes.spec.ts` + smoke; mocked eval/reviews flows |
| Locust | ~50 concurrent webhooks | **In-repo** [`loadtests/`](../loadtests/); **workflow** `.github/workflows/loadtest.yml` (`workflow_dispatch`) |
| Lighthouse | Score targets in PDF | **Advisory** step on dashboard workflow (not a hard gate) |
| Structured logging / correlation ID | PDF week 7 | **Partial** — request middleware; tune to your ops stack |
| Health | `/health` + components | **Yes** — `/health`, `/livez`, `/readyz` |
| Ship week 8 | Live URLs, video, blog, HN | **Outside repo** — [`PUBLISHING_AND_BENCHMARK.md`](PUBLISHING_AND_BENCHMARK.md), [`DEPLOY.md`](DEPLOY.md), drafts in `docs/` |

## Success metrics (PDF page 12)

Honest reporting beats inflated F1. Targets are **aspirational** until you run a **real** labeled eval (not the default mock-aligned bundle).

| Metric | PDF target | Notes |
|--------|------------|--------|
| Security / bug F1 | Thresholds in PDF | Measure with **your** labels + `eval_runner.py` |
| Latency / cost | PDF caps | Observable via API + costs pages |
| Lighthouse | >90 aspirational | Run `npm run lh:advisory` locally; CI step is advisory |

## Outside-repo work

| Work | Doc |
|------|-----|
| Deploy, blog, video, hand-labeled benchmark | [`PUBLISHING_AND_BENCHMARK.md`](PUBLISHING_AND_BENCHMARK.md) |
| Infra | [`DEPLOY.md`](DEPLOY.md) |
