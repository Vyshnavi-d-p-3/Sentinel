# Build document vs implementation (status)

This tracks the *Sentinel — Complete Build Document* (project proposal) against the repository. Update it when scope changes.

| Area | Spec | Status |
|------|------|--------|
| Core stack (FastAPI, Next 14, Postgres + pgvector, eval harness) | Yes | Shipped |
| Embeddings | Doc example: 1536-d OpenAI | **1024-d Voyage** (`EMBEDDING_MODEL` / `EMBEDDING_DIM`) — intentional |
| `GET/ PATCH /api/v1/repos` | List + per-repo settings | **Implemented** — see `/api/v1/repos/` and `PATCH /api/v1/repos/{id}/settings` |
| 100-PR eval dataset | 100 (min 50) | **In progress** — see `eval/fixtures/README.md` |
| Playwright E2E | Core flows | **Smoke (home only)** — `dashboard/e2e/`, `npm run test:e2e`. Use a **production** `next build` output (not mixed with `next dev --turbo`) or remove `.next` before e2e. |
| Locust load tests | 50 concurrent webhooks | Not automated in-repo |
| Public deploy (Railway/Fly + Vercel + Neon) | Yes | **Open** (README roadmap) |
| Blog + Loom + public App install | Yes | **Open** |

Success metrics in the spec (F1, latency, cost) require a **full** labeled run and a stable deployment — track those in eval results and ops notes, not only in code.
