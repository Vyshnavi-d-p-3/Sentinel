"""
Load-test GitHub webhooks: POST /webhook/github with a valid HMAC and JSON body.

Prerequisites:
- Backend running (e.g. ``uvicorn app.main:app`` from ``backend/``) with
  ``GITHUB_WEBHOOK_SECRET`` set to the same value as the Locust process.
- Raw diff available over HTTP: serve this directory::

    python -m http.server 9999

  so ``DIFF_FETCH_URL`` defaults to ``http://127.0.0.1:9999/static_pr.diff`` work.
- Postgres reachable with schema migrated (``DB_AUTO_CREATE_TABLES`` or Alembic).
- Raise the webhook rate limit for load, e.g. ``RATE_LIMIT_WEBHOOK=20000/minute``.

See ``loadtests/README.md`` for a full example.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import uuid

from locust import HttpUser, between, task

# Same secret the FastAPI app uses (see backend ``GITHUB_WEBHOOK_SECRET``).
WEBHOOK_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET", "dev-webhook-secret")
# Full URL the backend will GET to download the diff (must be network-reachable
# from the API process, not from Locust).
DIFF_FETCH_URL = os.environ.get(
    "DIFF_FETCH_URL",
    "http://127.0.0.1:9999/static_pr.diff",
)
# Synthetic GitHub repository id; stable is fine (one row per test repo).
REPO_GITHUB_ID = int(os.environ.get("LOADTEST_REPO_GITHUB_ID", "900000001"))


def _sign(body: bytes) -> str:
    mac = hmac.new(WEBHOOK_SECRET.encode("utf-8"), body, hashlib.sha256)
    return "sha256=" + mac.hexdigest()


def _payload(pr_num: int) -> dict:
    return {
        "action": "opened",
        "number": pr_num,
        "pull_request": {
            "number": pr_num,
            "title": "loadtest",
            "html_url": f"https://github.com/sentinel/loadtest/pull/{pr_num}",
            "diff_url": DIFF_FETCH_URL,
            "head": {"sha": "a" * 40},
        },
        "repository": {
            "id": REPO_GITHUB_ID,
            "full_name": "sentinel/loadtest",
        },
        "installation": {"id": 0},
    }


class WebhookUser(HttpUser):
    """Fires one webhook per task; 50+ concurrent users = concurrent deliveries."""

    wait_time = between(0.01, 0.05)
    pr_counter: int = 10_000_000

    @task
    def post_pull_request_opened(self) -> None:
        WebhookUser.pr_counter += 1
        pr_num = WebhookUser.pr_counter
        body = json.dumps(_payload(pr_num), separators=(",", ":"))
        body_bytes = body.encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": _sign(body_bytes),
            "X-GitHub-Delivery": str(uuid.uuid4()),
        }
        # Prefix from Locust --host, e.g. http://127.0.0.1:8000
        self.client.post("/webhook/github", data=body_bytes, headers=headers, name="webhook:pull_request")
