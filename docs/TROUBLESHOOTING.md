# Troubleshooting

## Next.js dev server: HTTP 500, “missing required error components, refreshing…”

This almost always means **Turbopack or a stale `.next` cache** left the dev server (`npm run dev`) in a bad state—not your application code.

**Fix (try in order):**

1. Stop the dev server (Ctrl+C).
2. Remove the cache: `cd dashboard && rm -rf .next`
3. Start again: `npm run dev` (default is the **Webpack** dev server; it is slower but more stable than Turbo on some macOS setups).
4. If you need Turbopack: `npm run dev:turbo`
5. **Nuclear option** (closest to production): `npm run build && npm start` — serves on port 3000 with no HMR.

If the page is still blank, open DevTools → **Console** and note the first red error before filing an issue.

## Dashboard “not loading,” blank data, or red error panels

The Next.js UI **does not embed** the Python API. In dev, `next.config.mjs` **rewrites** `/api/*` and `/health` to the backend URL (`NEXT_PUBLIC_API_URL`, default `http://localhost:8000`). If nothing listens there, the browser gets a **network error** and the home page shows **“Cannot reach the API”** on the health card.

**Fix (local):**

1. Start Postgres (or use Docker for the DB only / full stack).
2. From the repo root: `docker compose up --build` **or** manually:
   - Terminal A: `cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`
   - Terminal B: `cd dashboard && npm run dev`
3. Confirm: `curl -sS http://127.0.0.1:8000/health` returns JSON.

**Fix (API key):** If the backend has `API_KEY` set, the dashboard must send the same value: set `NEXT_PUBLIC_API_KEY` before `npm run dev` / Vercel build. Health is **not** key-protected; `/api/v1/*` **is** when `API_KEY` is set.

**Fix (HTTPS deploy):** A dashboard on **https://** cannot call an **http://** API from the browser (mixed content). Terminate TLS in front of both, or proxy the API under the same origin.

## Backend exits or /health shows database unavailable

- Check `DATABASE_URL` (async driver `postgresql+asyncpg://...`).
- Ensure Postgres is running and reachable.
- For hybrid retrieval, install **pgvector** on the server; without it, startup may log warnings and the health card can show embeddings index as missing (degraded, not necessarily down).

## Webhooks return 401

`POST /webhook/github` requires a valid `X-Hub-Signature-256` using `GITHUB_WEBHOOK_SECRET`. A wrong secret or body mutation (e.g. proxy re-encoding JSON) will fail verification.

## Still stuck

Note your environment: local vs Vercel, `NEXT_PUBLIC_API_URL` value, and whether `curl` to that URL + `/health` works from the same machine the browser uses.
