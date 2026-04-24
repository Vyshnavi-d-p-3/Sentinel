# Troubleshooting

## The application is not running (nothing on :3000 / :8000)

Work through this in order:

1. **Postgres** — The API needs a database. `DATABASE_URL` in `backend/.env` must point to a **running** server (default in `.env.example` is `127.0.0.1:5432`).  
   - With Docker: `docker compose up -d db` (from repo root) or full stack: `docker compose up --build`.  
   - Without Docker: install Postgres locally and create DB/user, or `brew services start postgresql@16` (example).

2. **Backend** — From `backend/`: venv + `pip install -r requirements.txt`, then `alembic upgrade head` (or `DB_AUTO_CREATE_TABLES=true` once).  
   Test: `curl -sS http://127.0.0.1:8000/health` should return JSON.

3. **Dashboard** — From `dashboard/`: `npm install`, then `npm run dev` (or use **root** `npm run dev` — see main README).  
   Test: open `http://127.0.0.1:3000` (not 0.0.0.0 in some VPN setups—try `127.0.0.1`).

4. **Port conflicts** — If something else uses 3000 or 8000, stop it or set `PORT=3001` for Next and `--port 8001` for uvicorn (and set `NEXT_PUBLIC_API_URL` / dashboard `.env.local` to match the API port).

5. **Still stuck** — Paste the **first error** from the terminal where you started the backend and from `dashboard` (or from `npm run dev` at repo root).

## Home page is 404 in `next dev` (EMFILE / “too many open files, watch”)

On **macOS**, the default file watcher can hit the `ulimit` and **fail to see `app/page.tsx`**, so `/` renders as **404** while `/health` still proxies fine. The terminal shows `Watchpack Error (watcher): EMFILE`.

**Fix:** The dashboard `npm run dev` script enables **polling** (`WATCHPACK_POLLING=true`) to avoid this. If you still see EMFILE, raise the limit for the shell: `ulimit -n 10240`, or use production mode: `npm run build && npm start`.

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
