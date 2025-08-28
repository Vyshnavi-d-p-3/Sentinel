"""GitHub App JWT + installation access token (for authenticated API calls)."""

from __future__ import annotations

import logging
import time
from pathlib import Path

import httpx
import jwt

from app.config import settings

logger = logging.getLogger(__name__)


def _app_jwt() -> str | None:
    app_id = settings.github_app_id.strip()
    if not app_id:
        return None
    key_path = Path(settings.github_private_key_path)
    if not key_path.is_file():
        logger.debug("GitHub private key not found at %s", key_path)
        return None
    private_key = key_path.read_text()
    now = int(time.time())
    payload = {"iat": now - 60, "exp": now + 600, "iss": app_id}
    return jwt.encode(payload, private_key, algorithm="RS256")


async def get_installation_access_token(installation_id: int) -> str | None:
    """
    Return a short-lived installation token, or None if the app is not configured.

    Used to fetch private diffs and (later) post reviews.
    """
    token = _app_jwt()
    if not token:
        return None
    url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return str(data.get("token", "")) or None
    except Exception as exc:
        logger.warning("Could not mint installation token: %s", exc)
        return None
