# Build document vs implementation (status)

Tracking the *Sentinel — Complete Build Document* against the repository.

| Area | Spec | Status |
|------|------|--------|
| Core stack (FastAPI, Next 14, Postgres + pgvector, eval harness) | Yes | Shipped |
| Embeddings | Doc example: 1536-d OpenAI | **1024-d Voyage** — intentional |
| `GET/ PATCH /api/v1/repos` | List + per-repo settings | **Implemented** |
| 100-PR eval dataset | 100 (min 50) | **100 × `synth_pr_*.json`** (mock‑aligned for CI); **hand examples** in `eval/fixtures/legacy/` |
| Playwright E2E | Core flows | **Home smoke** — `dashboard/e2e/` |
| Locust load tests | 50 concurrent webhooks | **In-repo** — [`loadtests/`](../loadtests/) (manual / staging; not in CI) |
| Public deploy (Railway/Fly + Vercel + Neon) | Yes | **Documented** — [`DEPLOY.md`](DEPLOY.md) |
| Blog + Loom + public App install | Yes | **Drafts** — [`BLOG_DRAFT.md`](BLOG_DRAFT.md), [`VIDEO_OUTLINE.md`](VIDEO_OUTLINE.md); install = follow `DEPLOY.md` + GitHub App |

Success metrics (F1, latency, cost) under **real** LLM keys are for you to measure after deploy; the **mock** harness now reports **strict F1 = 1.0** on the synthetic set by construction.
