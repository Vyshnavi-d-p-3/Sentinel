# Deploy Sentinel (Vercel + Railway/Fly + Neon)

This is the **reference path** to ship the build document’s “public URLs” target. It is not a single vendor template—wire secrets in each dashboard.

## 1. Database (Neon, Supabase, or RDS)

1. Create a **Postgres 16+** project with the **pgvector** extension.
2. Run migrations from your laptop or CI:  
   `cd backend && alembic upgrade head`  
   (set `DATABASE_URL` to the connection string, async driver `postgresql+asyncpg://...`)
3. In production set `DB_AUTO_CREATE_TABLES=false` after migrations.

## 2. Backend (Railway or Fly)

**Environment (minimum):**

- `DATABASE_URL` — same as above
- `ENVIRONMENT=production`
- `API_KEY` — long random string; mirror on the dashboard as `NEXT_PUBLIC_API_KEY` if you use browser-side calls
- `GITHUB_WEBHOOK_SECRET`, `GITHUB_APP_ID`, and private key for the GitHub App
- `CORS_ORIGINS` — JSON list including your Vercel origin, e.g. `["https://your-app.vercel.app"]`
- `LLM_MOCK_MODE=false` and real `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` as needed
- `VOYAGEAI_API_KEY` if using production embeddings

**Docker:** the repo’s `backend/Dockerfile` is the portable unit. On Railway, set root to `backend/`, or build from the repo root with `context: ./backend` as in CI.

**Health:** your platform’s health check should call `GET /health` (or `/livez` for liveness only).

## 3. Dashboard (Vercel)

1. **Import** the `dashboard` folder as a Next.js app.
2. **Environment variables**  
   - `NEXT_PUBLIC_API_URL` — your **public** API origin, e.g. `https://api.yourdomain.com` (the UI calls this; CORS and rewrites use it).  
   - Optional: `NEXT_PUBLIC_API_KEY` to match the backend `API_KEY`.
3. The app uses **Next rewrites** (`next.config.mjs`) to proxy `/api/*` to `NEXT_PUBLIC_API_URL`. In production, either keep that URL as the same host behind a reverse proxy, or set `NEXT_PUBLIC_API_URL` to the FastAPI service URL.

4. **Build:** Vercel uses `next build` automatically; the Dockerfile’s `STANDALONE_BUILD=1` is for container deploys only.

## 4. GitHub App

- Webhook URL: `https://<api-host>/webhook/github` (or `/webhook/github` behind your path prefix).
- Use the same **webhook secret** as `GITHUB_WEBHOOK_SECRET`.

## 5. One-command local parity

`docker compose up --build` from the repo root still gives **db + API + UI** for demos without cloud accounts.

---

For a **single-host** production box, you can also run the published Docker images and a managed Postgres; the compose file in the repo is the source of truth for service wiring.
