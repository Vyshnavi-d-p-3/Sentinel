# Contributing to Sentinel

Thanks for your interest! This is a personal portfolio project, but PRs are
welcome — especially around the eval harness, additional language support for
the chunker, and dashboard polish.

## Local setup

```bash
git clone https://github.com/Vyshnavi-d-p-3/sentinel.git
cd sentinel
cp .env.example .env

# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head        # or DB_AUTO_CREATE_TABLES=true on first boot
uvicorn app.main:app --reload

# Dashboard (separate shell)
cd dashboard && npm install && npm run dev
```

You can also boot the whole stack with one command:

```bash
docker compose up --build
```

Without Docker (Postgres on localhost), from the **repo root** after
`backend` venv + `dashboard` `npm install` are set up: `npm install && npm run dev`
(see the main [README](README.md#quick-start)).

## Workflow

1. Fork the repo and create a feature branch off `main`.
2. Make your change. Add tests — the bar is "every router and service has a
   unit test, every endpoint has at least a happy-path integration test".
3. Run the local checks:
   ```bash
   cd backend && pytest -q && ruff check .
   cd ../dashboard && npm run lint && npm run typecheck && npm run build
   ```
4. (Optional but recommended) install pre-commit hooks:
   ```bash
   pip install pre-commit && pre-commit install
   ```
5. Open a PR with a clear description and the rationale (what, why, trade-offs).

## Project documentation

Eval methodology, deploy, and *off-repo* deliverables (blog, video, real benchmarks) are indexed from the [root README](README.md#documentation) and in [`docs/PUBLISHING_AND_BENCHMARK.md`](docs/PUBLISHING_AND_BENCHMARK.md). When you change the eval harness, update [`eval/README.md`](eval/README.md) if you add scripts or change fixture layout.

## Code style

- Python: ruff-formatted, type hints everywhere, prefer `from __future__ import
  annotations`. See `backend/pyproject.toml` for the lint config.
- TypeScript: Next.js + ESLint defaults, strict TS (`tsc --noEmit` must pass).
- Comments should explain *why*, not *what*. The code is the *what*.

## Adding a new dashboard page

1. Define the data contract in `dashboard/src/lib/types.ts`.
2. Add a hook in `dashboard/src/hooks/`.
3. Add a page under `dashboard/src/app/<slug>/page.tsx`.
4. Wire it into `dashboard/src/components/nav.tsx`.

## Adding a backend endpoint

1. Define the Pydantic request/response models inline (or in
   `app/models/`).
2. Add the router in `app/routers/<feature>.py`.
3. Mount it in `app/main.py` under the `/api/v1/<feature>` prefix and (if it's
   for the dashboard) include the `require_api_key` dependency.
4. Write a unit test in `backend/tests/unit/test_<feature>.py`.

## Reporting bugs

Open a GitHub issue with:
- Sentinel version (or commit SHA)
- Reproduction steps
- Expected vs. actual behavior
- Logs (with secrets redacted)

For security vulnerabilities see [SECURITY.md](./SECURITY.md).
