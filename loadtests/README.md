# Webhook load tests (Locust)

Exercises `POST /webhook/github` with HMAC-valid payloads so you can approach **~50 concurrent in-flight** deliveries (per the build doc). The API still **GETs the diff** from a URL (`pull_request.diff_url`); for local tests, serve a static diff from this directory.

## Setup (four terminals)

1. **Postgres** — e.g. Docker Compose or local Postgres, DB URL in `backend/.env` (`DATABASE_URL`).

2. **Static diff** — from the **repo root**:

   ```bash
   python -m http.server 9999 --directory loadtests
   ```

   Serves `static_pr.diff` at `http://127.0.0.1:9999/static_pr.diff`.

3. **Backend** — from `backend/` with mock LLM and a loose webhook cap:

   ```bash
   export LLM_MOCK_MODE=true
   export GITHUB_WEBHOOK_SECRET=dev-webhook-secret
   export RATE_LIMIT_WEBHOOK=20000/minute
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

4. **Locust** — from repo root (use a venv with `loadtests/requirements.txt` or `pip install locust`):

   ```bash
   export GITHUB_WEBHOOK_SECRET=dev-webhook-secret
   export DIFF_FETCH_URL=http://127.0.0.1:9999/static_pr.diff
   locust -f loadtests/locustfile.py --host http://127.0.0.1:8000
   ```

   In the web UI, start **50 users**, spawn rate **5–10/s**, and watch response times. Each request must use a **unique** `X-GitHub-Delivery` and PR number; the `locustfile` does that automatically.

## Environment

| Variable | Default | Purpose |
|----------|---------|--------|
| `GITHUB_WEBHOOK_SECRET` | `dev-webhook-secret` | Must match the API |
| `DIFF_FETCH_URL` | `http://127.0.0.1:9999/static_pr.diff` | URL the **backend** fetches (localhost is fine) |
| `LOADTEST_REPO_GITHUB_ID` | `900000001` | Synthetic `repository.id` in the JSON body |

## CI

This flow is not run in GitHub Actions (needs long-lived server + high concurrency). It is for manual or staging load verification.
