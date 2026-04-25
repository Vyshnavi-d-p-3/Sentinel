# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

- **Eval:** Replaced 100 mock-aligned `synth_pr_*.json` fixtures with 98 realistic `pr_*.json` files from `eval/scripts/generate_realistic_fixtures.py`; `is_clean` supported in fixtures; placeholder `eval/baselines/baseline.json` for CI gate. GitHub client posts inline comments via batch PR Review API with fallback. Added deploy templates (`Procfile`, `fly.toml`, `vercel.json`), `docs/GITHUB_APP_SETUP.md`, and expanded Playwright coverage (`e2e/pages.spec.ts`).

### 2026-04-24

- **Dev UX:** root `package.json` with `concurrently` — `npm run dev` runs API + dashboard; `package-lock.json` at repo root.
- **Dashboard:** `WATCHPACK_POLLING=true` in default `npm run dev` to avoid macOS `EMFILE` and bogus `/` 404; `dev:turbo` for optional Turbopack.
- **Docs:** `docs/TROUBLESHOOTING.md` (connectivity, Next 500, EMFILE), `docs/PUBLISHING_AND_BENCHMARK.md`, README Quick Start (Docker / one-terminal / two-terminal), `eval/README.md` hub, error hints when the API is unreachable.

### Added

- **Security middleware stack**
  - `RequestIDMiddleware` — propagates / generates `X-Request-ID` for log
    correlation.
  - `SecurityHeadersMiddleware` — adds `X-Content-Type-Options`,
    `X-Frame-Options`, `Referrer-Policy`, `Cross-Origin-Opener-Policy`,
    `Cross-Origin-Resource-Policy`, `Permissions-Policy`.
  - `BodySizeLimitMiddleware` — rejects requests larger than
    `MAX_REQUEST_BODY_BYTES` (default 2 MiB) with HTTP 413.
  - `AccessLogMiddleware` — one structured log line per request with stable
    request ID, latency, status, and client IP.
- **Optional API-key authentication** for `/api/v1/*` dashboard endpoints
  (`X-API-Key` or `Authorization: Bearer`).
- **Per-IP rate limiting** via `slowapi`: 120/min default, 60/min on the
  webhook, 10/min on the public preview endpoint.
- **Webhook idempotency** via an in-memory TTL-LRU keyed on
  `X-GitHub-Delivery` so retried deliveries don't duplicate work.
- **LLM call timeouts** (`LLM_CALL_TIMEOUT_SEC`, default 60s) and per-prompt
  size caps to prevent runaway cost.
- **Startup config validation** — refuses to boot in
  `ENVIRONMENT=production` without a webhook secret or LLM keys.
- **Structured JSON logs** when `SENTINEL_LOG_FORMAT=json`.
- **Liveness (`/livez`) and readiness (`/readyz`) probes** alongside the
  existing dependency `/health` endpoint.
- **Hardened Dockerfiles** — multi-stage builds for both backend and
  dashboard, non-root user, `tini` as PID 1, in-container `HEALTHCHECK`.
- **Production `next.config.mjs`** — `output: "standalone"`,
  `poweredByHeader: false`, security response headers.
- **Hardened `docker-compose.yml`** — env-file driven, healthchecks
  everywhere, dashboard service, internal/public networks.
- **Alembic baseline migration** (`0001_initial_schema`) covering all ORM
  models including the pgvector extension and ivfflat index.
- **Tooling**: `pyproject.toml` with ruff/mypy/pytest config, top-level
  `.pre-commit-config.yaml` with ruff + gitleaks.
- **Operator docs**: `SECURITY.md`, `CONTRIBUTING.md`, `.env.example`,
  expanded README "Deployment" and "Security" sections.

### Changed

- **CORS** is now method/header-explicit; `OPTIONS` handling stays
  permissive but `*` wildcards are gone.
- **Webhook router** acks GitHub `ping` events explicitly and now also
  accepts `reopened` PRs.
- **`/health` payload** includes the active `environment` so the dashboard
  can warn when the backend is in development mode.
- **Repo walker CLI** verifies every yielded path resolves under the repo
  root (defense-in-depth against bind-mount escape).

### Security

- Empty webhook bodies are now rejected with HTTP 400 (previously processed
  as zero-length signatures).
- Incoming `X-Request-ID` headers are validated (alphanum / `-_`, ≤ 64
  chars) before being echoed in logs to prevent header-injection.
- Secrets in `app.config.Settings` are no longer included in the
  `/api/v1/config` response — only their `has_*` boolean status.

## [0.1.0] - 2026-04-14

Initial scaffolding: FastAPI backend, Next.js 14 dashboard, hybrid retrieval
(BM25 + pgvector with RRF fusion), 4-step agentic review pipeline, hand-labeled
98-PR (default) evaluation harness with per-category P/R/F1 and CI regression gate.
