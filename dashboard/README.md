# Sentinel Dashboard

Next.js 14 (App Router) + TanStack Query v5 + Tailwind. Thin read-only view over the FastAPI backend.

## Setup

```bash
cd dashboard
npm install
npm run dev
```

The dashboard expects the backend to be reachable at `NEXT_PUBLIC_API_URL`
(default `http://localhost:8000`). All `/api/*` and `/health` requests are
proxied via `next.config.mjs` rewrites, so the dashboard itself has no CORS
concerns.

## Pages

- `/` — home: health + KPI tiles + links into each subsection.
- `/reviews` — paginated list of reviews with filters and a detail drawer.
- `/reviews/[id]` — single review: summary, comments, pipeline telemetry.
- `/eval` — eval runs + per-category F1 (disk/DB); numbers may reflect **synthetic+mock** CI or separate **real-LLM** runs—see repo root **Evaluation** and `docs/PUBLISHING_AND_BENCHMARK.md`.
- `/costs` — daily spend and model/provider mix (reads `/api/v1/costs`).
- `/prompts` — active prompts + hashes (reads `/api/v1/prompts`).
- `/feedback` — online agreement-rate stats (reads `/api/v1/feedback/stats`).
- `/settings` — non-secret **config** snapshot (`/api/v1/config`) and **per-repo** settings (`/api/v1/repos`, `PATCH` for budgets / `auto_review`).
- `/try-review` — `POST` preview to `/api/v1/reviews/preview` (no GitHub event).

## Layout

```
src/
  app/                — App Router pages and route handlers
  components/         — small presentational components (no data fetching)
  hooks/              — TanStack Query hooks (one per endpoint family)
  lib/                — typed API client, helpers, constants
```

## Commands

```bash
npm run dev        # dev server
npm run build      # production build
npm run typecheck  # tsc --noEmit
npm run lint       # next lint
```
