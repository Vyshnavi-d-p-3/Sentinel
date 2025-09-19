# Security Policy

## Reporting a Vulnerability

If you believe you've found a security issue in Sentinel, please **do not file
a public GitHub issue**. Instead, email the maintainer directly with:

- A description of the issue and its impact
- Steps to reproduce (or a proof-of-concept)
- Any suggested mitigation

You can expect an acknowledgement within **3 business days** and a remediation
plan within **14 days** for confirmed issues. Sentinel is a personal portfolio
project; there's no formal bug bounty, but you'll be credited in the changelog.

## Threat Model

Sentinel is a GitHub App that ingests untrusted unified diffs, runs them
through an LLM pipeline, and persists the results. The trust boundaries are:

| Surface                           | Trust assumption                                     |
|-----------------------------------|------------------------------------------------------|
| `POST /webhook/github`            | Untrusted body, authenticated via HMAC-SHA256        |
| `GET /api/v1/*` (dashboard)       | Authenticated by API key (when `API_KEY` is set)     |
| `POST /api/v1/reviews/preview`    | Untrusted body, rate-limited per IP                  |
| LLM provider responses            | Treated as untrusted text, validated against Pydantic|
| Local repo checkout (CLI)         | Trusted by operator running the CLI                  |
| Postgres                          | Trusted (private network)                            |

## Built-in Defenses

- **HMAC webhook authentication** — `app/core/security.py` uses
  `hmac.compare_digest` to defeat timing attacks on `X-Hub-Signature-256`.
- **Webhook idempotency** — `X-GitHub-Delivery` keyed cache stops retried
  deliveries from re-running the pipeline (`app/core/idempotency.py`).
- **API-key auth** for the dashboard surface (`app/core/auth.py`). When
  `API_KEY` is unset, the API is open — fine for local dev, **must** be set in
  production.
- **Rate limiting** via `slowapi` on every public endpoint — defaults are
  120/min global, 60/min on the webhook, 10/min on the preview endpoint.
- **Body-size middleware** rejects requests above 2 MiB by default
  (`MAX_REQUEST_BODY_BYTES`).
- **Security headers** — `X-Content-Type-Options`, `X-Frame-Options`,
  `Referrer-Policy`, `Cross-Origin-Opener-Policy`, `Permissions-Policy` are
  applied to every response by both the FastAPI middleware and the Next.js
  dashboard's `next.config.mjs`.
- **CORS allow-list** — explicit methods, headers, and origins; no wildcards
  in production.
- **LLM call timeouts** (`LLM_CALL_TIMEOUT_SEC`, default 60s) and per-prompt
  size caps prevent a hung upstream from pinning a worker forever.
- **Cost guard** — daily token budgets, per-PR caps, and a circuit breaker
  block runaway spend even if the LLM gateway misbehaves.
- **Path-traversal guards** in the repo-walker CLI (`relative_to` plus a
  symlink filter).
- **Container hardening** — both Dockerfiles run as a non-root user, expose a
  `HEALTHCHECK`, and use `tini` as PID 1 so SIGTERM drains in-flight requests.
- **Structured access logs** with stable `X-Request-ID` correlation IDs;
  query strings and request bodies are *not* logged.
- **Startup validation** — `validate_settings_for_runtime()` raises on missing
  webhook secrets / LLM keys when `ENVIRONMENT=production`.

## Known Limitations

- The idempotency cache is process-local. For multi-replica deployments swap
  it for a Redis-backed implementation.
- The cost guard is in-memory and resets on restart. Production should persist
  the daily window to Postgres.
- Background webhook tasks run inside the FastAPI process. For at-least-once
  semantics across restarts, move to a durable queue (Redis Streams, SQS).
- The dashboard does not implement an OAuth / SSO flow — auth is a single
  shared API key. Suitable for one-operator demos; replace with a real IdP
  before exposing to a team.

## Hardening Checklist for Operators

- [ ] Set `ENVIRONMENT=production`.
- [ ] Set `API_KEY` to a high-entropy random string (>= 32 bytes).
- [ ] Set `GITHUB_WEBHOOK_SECRET` and configure the same value in your GitHub
      App settings.
- [ ] Set explicit `CORS_ORIGINS` (HTTPS only).
- [ ] Disable `DB_AUTO_CREATE_TABLES` and run `alembic upgrade head` instead.
- [ ] Configure `SENTINEL_LOG_FORMAT=json` so logs ship to your aggregator
      cleanly.
- [ ] Run behind a reverse proxy that terminates TLS, sets `X-Forwarded-For`,
      and enforces request quotas.
- [ ] Pin `DEFAULT_MODEL` and `FALLBACK_MODEL` to specific versions so prompt
      regressions are isolated to dataset/prompt changes.
- [ ] Rotate the API key, webhook secret, and GitHub private key on a fixed
      schedule (90 days recommended).
