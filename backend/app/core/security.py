"""Webhook signature validation using HMAC-SHA256."""

import hashlib
import hmac

from app.config import settings


def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    """
    Verify GitHub webhook HMAC-SHA256 signature.

    GitHub sends X-Hub-Signature-256: sha256=<hex>
    We compute HMAC of raw payload and do constant-time comparison.
    """
    if not signature.startswith("sha256="):
        return False

    expected = hmac.new(
        settings.github_webhook_secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, signature[7:])
